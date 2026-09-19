"""幂等层测试：复用、重放、并发单执行、过期重跑。"""

import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone

from idemkit import Dispatcher, IdempotentSubmitter


class FakeClock:
    def __init__(self, start):
        self.now = start

    def __call__(self):
        return self.now


class IdemCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="idem-test-")

    def make(self, dispatcher=None, ttl=3600, clock=None):
        kwargs = {"ttl": ttl}
        if clock is not None:
            kwargs["clock"] = clock
        return IdempotentSubmitter(dispatcher or Dispatcher(), self.tmp, **kwargs)

    def store_files(self):
        return [
            n
            for n in os.listdir(self.tmp)
            if n.startswith("idem-") and n.endswith(".json")
        ]


class TestSameKeyReuse(IdemCase):
    def test_same_key_returns_first_result_and_runs_once(self):
        calls = []
        d = Dispatcher()
        d.register("render", lambda p: calls.append(p) or {"thumb": "a.jpg"})
        s = self.make(d)

        first = s.submit("k-1", "render", {"name": "a.png"})
        second = s.submit("k-1", "render", {"name": "a.png"})

        self.assertEqual(first, {"thumb": "a.jpg"})
        self.assertEqual(second, first)
        self.assertEqual(calls, [{"name": "a.png"}])
        self.assertEqual(len(self.store_files()), 1)

    def test_different_keys_run_separately(self):
        calls = []
        d = Dispatcher()
        d.register("echo", lambda p: calls.append(p) or p)
        s = self.make(d)

        self.assertEqual(s.submit("k-a", "echo", {"n": 1}), {"n": 1})
        self.assertEqual(s.submit("k-b", "echo", {"n": 2}), {"n": 2})
        self.assertEqual(len(calls), 2)

    def test_record_persists_key_result_and_expiry(self):
        d = Dispatcher()
        d.register("echo", lambda p: p)
        s = self.make(d, ttl=100)
        s.submit("k-file", "echo", {"ok": True})

        path = os.path.join(self.tmp, self.store_files()[0])
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        self.assertEqual(record["idem_key"], "k-file")
        self.assertEqual(record["task_name"], "echo")
        self.assertEqual(record["result"], {"ok": True})
        self.assertIn("expires_at", record)
        created = datetime.fromisoformat(record["created_at"])
        expires = datetime.fromisoformat(record["expires_at"])
        self.assertEqual(expires - created, timedelta(seconds=100))


class TestRestartReplay(IdemCase):
    def test_new_instance_same_dir_replays_without_dispatch(self):
        d1 = Dispatcher()
        d1.register("render", lambda p: {"thumb": "x.jpg"})
        s1 = self.make(d1)
        first = s1.submit("restart-1", "render", {"name": "x.png"})

        d2 = Dispatcher()  # 不注册任何任务：若误走 dispatch 必抛 UnknownTaskError
        s2 = self.make(d2)
        replayed = s2.submit("restart-1", "render", {"name": "x.png"})

        self.assertEqual(replayed, first)
        self.assertEqual(len(self.store_files()), 1)


class TestConcurrentSameKey(IdemCase):
    def test_concurrent_same_key_executes_once(self):
        entered = threading.Event()
        proceed = threading.Event()
        release = threading.Event()
        runs = []
        results = {}

        def handler(payload):
            runs.append(payload)
            entered.set()
            proceed.wait(timeout=5)
            return {"thumb": "only.jpg", "by": payload["by"]}

        d = Dispatcher()
        d.register("render", handler)
        s = self.make(d)

        def worker(idx):
            release.wait(timeout=5)
            results[idx] = s.submit("hot-key", "render", {"by": idx})

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        release.set()

        self.assertTrue(entered.wait(timeout=5))
        self.assertEqual(len(runs), 1)
        proceed.set()
        for t in threads:
            t.join(timeout=5)
            self.assertFalse(t.is_alive())

        self.assertEqual(len(runs), 1)
        self.assertEqual(
            results,
            {i: {"thumb": "only.jpg", "by": runs[0]["by"]} for i in range(4)},
        )
        self.assertEqual(len(self.store_files()), 1)


class TestExpiry(IdemCase):
    def test_expired_key_reruns_and_replaces_file(self):
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        clock = FakeClock(start)
        calls = []
        d = Dispatcher()
        d.register("render", lambda p: calls.append(p) or {"at": str(clock.now)})
        s = self.make(d, ttl=10, clock=clock)

        first = s.submit("ttl-1", "render", {})
        self.assertEqual(len(calls), 1)

        clock.now = start + timedelta(seconds=5)
        self.assertEqual(s.submit("ttl-1", "render", {}), first)
        self.assertEqual(len(calls), 1)

        clock.now = start + timedelta(seconds=11)
        second = s.submit("ttl-1", "render", {})
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(second, first)
        self.assertEqual(len(self.store_files()), 1)

    def test_lazy_sweep_removes_expired_on_unrelated_submit(self):
        start = datetime(2026, 9, 20, tzinfo=timezone.utc)
        clock = FakeClock(start)
        d = Dispatcher()
        d.register("echo", lambda p: p)
        s = self.make(d, ttl=10, clock=clock)

        s.submit("old-1", "echo", {})
        s.submit("old-2", "echo", {})
        self.assertEqual(len(self.store_files()), 2)

        clock.now = start + timedelta(seconds=20)
        s.submit("fresh", "echo", {})

        remaining = []
        for n in self.store_files():
            with open(os.path.join(self.tmp, n), encoding="utf-8") as f:
                remaining.append(json.load(f))
        self.assertEqual([r["idem_key"] for r in remaining], ["fresh"])


if __name__ == "__main__":
    unittest.main()
