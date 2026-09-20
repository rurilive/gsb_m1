"""IdempotentSubmitter 行为测试：同键复用、重启重放、并发单执行、过期重跑。"""

import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from idemkit import Dispatcher, IdempotentSubmitter


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class IdemTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store_dir = self.tmp.name
        self.calls = []
        self.dispatcher = Dispatcher()
        self.dispatcher.register("add", self._add)

    def _add(self, payload):
        self.calls.append(payload)
        return {"sum": payload["a"] + payload["b"]}

    def make_submitter(self, ttl=60, clock=None):
        return IdempotentSubmitter(
            self.dispatcher, self.store_dir, ttl, clock=clock
        )


class TestSameKeyReuse(IdemTestCase):
    def test_same_key_returns_first_result_without_rerun(self):
        sub = self.make_submitter()
        r1 = sub.submit("job-1", "add", {"a": 1, "b": 2})
        r2 = sub.submit("job-1", "add", {"a": 1, "b": 2})
        r3 = sub.submit("job-1", "add", {"a": 9, "b": 9})
        self.assertEqual(r1, {"sum": 3})
        self.assertEqual(r2, r1)
        self.assertEqual(r3, r1)
        self.assertEqual(len(self.calls), 1)

    def test_different_keys_run_independently(self):
        sub = self.make_submitter()
        r1 = sub.submit("job-1", "add", {"a": 1, "b": 2})
        r2 = sub.submit("job-2", "add", {"a": 1, "b": 2})
        self.assertEqual(r1, r2)
        self.assertEqual(len(self.calls), 2)

    def test_result_persisted_with_key_and_expiry(self):
        clock = FakeClock()
        sub = self.make_submitter(ttl=60, clock=clock)
        sub.submit("job-1", "add", {"a": 1, "b": 2})
        files = list(Path(self.store_dir).glob("*.json"))
        self.assertEqual(len(files), 1)
        entry = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(entry["key"], "job-1")
        self.assertEqual(entry["task_name"], "add")
        self.assertEqual(entry["result"], {"sum": 3})
        self.assertEqual(entry["expires_at"], 1000.0 + 60)


class TestRestartReplay(IdemTestCase):
    def test_new_instance_replays_from_disk(self):
        clock = FakeClock()
        sub1 = self.make_submitter(ttl=60, clock=clock)
        r1 = sub1.submit("job-1", "add", {"a": 1, "b": 2})
        self.assertEqual(len(self.calls), 1)

        # 模拟进程重启：新 Dispatcher + 新 Submitter，指向同一 store_dir
        calls2 = []
        dispatcher2 = Dispatcher()
        dispatcher2.register(
            "add", lambda p: calls2.append(p) or {"sum": -999}
        )
        sub2 = IdempotentSubmitter(
            dispatcher2, self.store_dir, 60, clock=clock
        )
        r2 = sub2.submit("job-1", "add", {"a": 1, "b": 2})
        self.assertEqual(r2, r1)
        self.assertEqual(calls2, [])


class TestConcurrentSameKey(IdemTestCase):
    def test_concurrent_same_key_executes_once(self):
        entered = threading.Event()
        release = threading.Event()
        runs = []

        def slow(payload):
            runs.append(payload)
            entered.set()
            self.assertTrue(release.wait(timeout=5))
            return {"n": len(runs)}

        dispatcher = Dispatcher()
        dispatcher.register("slow", slow)
        sub = IdempotentSubmitter(dispatcher, self.store_dir, 60)

        results = []
        errors = []

        def worker():
            try:
                results.append(sub.submit("job-1", "slow", {"x": 1}))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(timeout=5))
        time.sleep(0.1)
        release.set()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(len(runs), 1)
        self.assertEqual(results, [{"n": 1}] * 8)


class TestExpiry(IdemTestCase):
    def test_expired_key_reruns(self):
        clock = FakeClock()
        sub = self.make_submitter(ttl=10, clock=clock)
        r1 = sub.submit("job-1", "add", {"a": 1, "b": 2})
        clock.advance(11)
        r2 = sub.submit("job-1", "add", {"a": 1, "b": 2})
        self.assertEqual(r1, r2)
        self.assertEqual(len(self.calls), 2)

    def test_not_expired_key_does_not_rerun(self):
        clock = FakeClock()
        sub = self.make_submitter(ttl=10, clock=clock)
        sub.submit("job-1", "add", {"a": 1, "b": 2})
        clock.advance(9)
        sub.submit("job-1", "add", {"a": 1, "b": 2})
        self.assertEqual(len(self.calls), 1)

    def test_expired_entries_lazily_purged(self):
        clock = FakeClock()
        sub = self.make_submitter(ttl=10, clock=clock)
        sub.submit("job-1", "add", {"a": 1, "b": 2})
        self.assertEqual(len(list(Path(self.store_dir).glob("*.json"))), 1)
        clock.advance(11)
        sub.submit("job-2", "add", {"a": 3, "b": 4})
        remaining = [
            json.loads(p.read_text(encoding="utf-8"))["key"]
            for p in Path(self.store_dir).glob("*.json")
        ]
        self.assertEqual(remaining, ["job-2"])


if __name__ == "__main__":
    unittest.main()
