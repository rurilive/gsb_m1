"""IdempotentSubmitter 行为测试：同键复用、重启重放、并发单执行、过期重跑。"""

import json
import os
import tempfile
import threading
import unittest

from idemkit import Dispatcher, IdempotentSubmitter


class FakeClock:
    """可拨快的时钟，验证 TTL 过期。"""

    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestSameKeyReuse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.calls = []
        d = Dispatcher()
        d.register("work", self._work)
        self.sub = IdempotentSubmitter(d, self.tmp.name, ttl=60, clock=self.clock)

    def _work(self, payload):
        self.calls.append(payload)
        return {"n": len(self.calls), "payload": payload}

    def test_same_key_returns_first_result_without_rerun(self):
        r1 = self.sub.submit("k1", "work", {"x": 1})
        r2 = self.sub.submit("k1", "work", {"x": 1})
        self.assertEqual(r1, r2)
        self.assertEqual(len(self.calls), 1)

    def test_different_key_runs_again(self):
        self.sub.submit("k1", "work", {"x": 1})
        self.sub.submit("k2", "work", {"x": 1})
        self.assertEqual(len(self.calls), 2)

    def test_result_persisted_with_key_and_expiry(self):
        result = self.sub.submit("k1", "work", {"x": 1})
        names = [n for n in os.listdir(self.tmp.name) if n.endswith(".json")]
        self.assertEqual(len(names), 1)
        with open(os.path.join(self.tmp.name, names[0]), encoding="utf-8") as fh:
            record = json.load(fh)
        self.assertEqual(record["key"], "k1")
        self.assertEqual(record["result"], result)
        self.assertEqual(record["expires_at"], self.clock.now + 60)


class TestRestartReplay(unittest.TestCase):
    def test_new_instance_replays_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            calls = []
            d = Dispatcher()
            d.register("work", lambda p: calls.append(p) or {"echo": p})

            sub1 = IdempotentSubmitter(d, tmp, ttl=60, clock=clock)
            r1 = sub1.submit("k1", "work", {"x": 1})
            self.assertEqual(len(calls), 1)

            # 模拟进程重启：新实例指向同一 store_dir，内存缓存是空的
            sub2 = IdempotentSubmitter(d, tmp, ttl=60, clock=clock)
            r2 = sub2.submit("k1", "work", {"x": 1})
            self.assertEqual(r2, r1)
            self.assertEqual(len(calls), 1)


class TestConcurrentSameKey(unittest.TestCase):
    def test_runs_exactly_once_and_all_waiters_get_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            entered = threading.Event()
            release = threading.Event()
            calls = []

            def slow(payload):
                calls.append(payload)
                entered.set()
                self.assertTrue(release.wait(timeout=5))
                return {"done": payload}

            d = Dispatcher()
            d.register("slow", slow)
            sub = IdempotentSubmitter(d, tmp, ttl=60)

            results = []
            errors = []

            def worker():
                try:
                    results.append(sub.submit("k1", "slow", {"x": 1}))
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(5)]
            threads[0].start()
            self.assertTrue(entered.wait(timeout=5))  # 首线程已进入 handler
            for t in threads[1:]:
                t.start()  # 其余线程到来时首跑尚未结束，只能等结果
            release.set()
            for t in threads:
                t.join(timeout=5)

            self.assertEqual(errors, [])
            self.assertEqual(len(calls), 1)
            self.assertEqual(results, [{"done": {"x": 1}}] * 5)


class TestExpiry(unittest.TestCase):
    def test_expired_key_reruns_and_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            calls = []
            d = Dispatcher()
            d.register("work", lambda p: calls.append(p) or {"n": len(calls)})
            sub = IdempotentSubmitter(d, tmp, ttl=60, clock=clock)

            r1 = sub.submit("k1", "work", {"x": 1})
            clock.advance(30)
            self.assertEqual(sub.submit("k1", "work", {"x": 1}), r1)  # TTL 内仍复用
            self.assertEqual(len(calls), 1)

            clock.advance(31)  # 越过 TTL
            r3 = sub.submit("k1", "work", {"x": 1})
            self.assertEqual(len(calls), 2)
            self.assertNotEqual(r3, r1)

    def test_expired_entries_cleaned_lazily(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock = FakeClock()
            d = Dispatcher()
            d.register("work", lambda p: p)
            sub = IdempotentSubmitter(d, tmp, ttl=60, clock=clock)

            sub.submit("k1", "work", 1)
            self.assertEqual(len(os.listdir(tmp)), 1)
            clock.advance(61)  # k1 已过期，但没有后台线程，文件还在
            self.assertEqual(len(os.listdir(tmp)), 1)

            sub.submit("k2", "work", 2)  # 写入时顺手清理过期条目
            self.assertEqual(len(os.listdir(tmp)), 1)


if __name__ == "__main__":
    unittest.main()
