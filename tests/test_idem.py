"""IdempotentSubmitter 行为测试：同键复用、重启重放、并发单执行、过期重跑。"""

import json
import os
import tempfile
import threading
import time
import unittest

from idemkit import Dispatcher, IdempotentSubmitter


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class IdemTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []
        self.dispatcher = Dispatcher()
        self.dispatcher.register("work", self._work)

    def _work(self, payload):
        self.calls.append(payload)
        return {"run": len(self.calls), "payload": payload}

    def make_submitter(self, **kwargs):
        kwargs.setdefault("ttl", 60)
        return IdempotentSubmitter(self.dispatcher, self.tmp.name, **kwargs)


class TestSameKeyReuse(IdemTestBase):
    def test_same_key_returns_first_result_without_rerun(self):
        sub = self.make_submitter()
        r1 = sub.submit("key-1", "work", {"x": 1})
        r2 = sub.submit("key-1", "work", {"x": 1})
        self.assertEqual(r1, {"run": 1, "payload": {"x": 1}})
        self.assertEqual(r2, r1)
        self.assertEqual(len(self.calls), 1)

    def test_different_keys_run_separately(self):
        sub = self.make_submitter()
        r1 = sub.submit("key-1", "work", {"x": 1})
        r2 = sub.submit("key-2", "work", {"x": 1})
        self.assertNotEqual(r1, r2)
        self.assertEqual(len(self.calls), 2)


class TestReplayAfterRestart(IdemTestBase):
    def test_new_instance_replays_from_store_dir(self):
        sub = self.make_submitter()
        r1 = sub.submit("key-1", "work", {"x": 1})
        self.assertEqual(len(self.calls), 1)

        # 模拟进程重启：新 Dispatcher + 新 IdempotentSubmitter，同一 store_dir
        later_calls = []
        dispatcher2 = Dispatcher()
        dispatcher2.register(
            "work", lambda p: later_calls.append(p) or {"run": -1}
        )
        sub2 = IdempotentSubmitter(dispatcher2, self.tmp.name, ttl=60)
        r2 = sub2.submit("key-1", "work", {"x": 1})

        self.assertEqual(r2, r1)
        self.assertEqual(later_calls, [])

    def test_entry_file_records_key_and_expiry(self):
        clock = FakeClock()
        sub = self.make_submitter(clock=clock)
        sub.submit("key-1", "work", {"x": 1})
        names = [n for n in os.listdir(self.tmp.name) if n.endswith(".json")]
        self.assertEqual(len(names), 1)
        with open(os.path.join(self.tmp.name, names[0]), encoding="utf-8") as fh:
            entry = json.load(fh)
        self.assertEqual(entry["key"], "key-1")
        self.assertEqual(entry["task_name"], "work")
        self.assertEqual(entry["expires_at"], clock.now + 60)
        self.assertEqual(entry["result"], {"run": 1, "payload": {"x": 1}})


class TestConcurrentSameKey(IdemTestBase):
    def test_concurrent_same_key_executes_once(self):
        started = threading.Event()
        release = threading.Event()
        slow_calls = []

        def slow(payload):
            slow_calls.append(payload)
            started.set()
            self.assertTrue(release.wait(timeout=5))
            return {"run": len(slow_calls)}

        dispatcher = Dispatcher()
        dispatcher.register("slow", slow)
        sub = IdempotentSubmitter(dispatcher, self.tmp.name, ttl=60)

        results = []
        errors = []

        def submit():
            try:
                results.append(sub.submit("key-1", "slow", {"x": 1}))
            except Exception as exc:  # pragma: no cover - 失败时暴露原因
                errors.append(exc)

        t1 = threading.Thread(target=submit)
        t1.start()
        self.assertTrue(started.wait(timeout=5))
        t2 = threading.Thread(target=submit)
        t2.start()
        time.sleep(0.1)  # 让 t2 赶到锁前等待首跑结果
        release.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(len(slow_calls), 1)
        self.assertEqual(sorted(map(str, results)), [str({"run": 1})] * 2)


class TestExpiryAndRerun(IdemTestBase):
    def test_expired_key_reruns_and_refreshes_entry(self):
        clock = FakeClock()
        sub = self.make_submitter(clock=clock)

        r1 = sub.submit("key-1", "work", {"x": 1})
        clock.advance(30)  # TTL 内：仍复用首跑结果
        self.assertEqual(sub.submit("key-1", "work", {"x": 1}), r1)
        self.assertEqual(len(self.calls), 1)

        clock.advance(31)  # 越过 TTL：惰性清理后重跑
        r2 = sub.submit("key-1", "work", {"x": 1})
        self.assertEqual(r2, {"run": 2, "payload": {"x": 1}})
        self.assertEqual(len(self.calls), 2)

        # 过期文件被清掉，目录里只剩重跑后的新条目
        names = [n for n in os.listdir(self.tmp.name) if n.endswith(".json")]
        self.assertEqual(len(names), 1)
        with open(os.path.join(self.tmp.name, names[0]), encoding="utf-8") as fh:
            entry = json.load(fh)
        self.assertEqual(entry["expires_at"], clock.now + 60)


if __name__ == "__main__":
    unittest.main()
