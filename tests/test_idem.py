"""IdempotentSubmitter 行为测试。"""

import os
import tempfile
import threading
import unittest

from idemkit import Dispatcher, IdempotentSubmitter


class FakeClock:
    """可拨快的时钟，用于验证过期重跑。"""

    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_dispatcher(calls):
    """注册一个计数 render handler，结果带执行序号以区分首跑与重跑。"""
    d = Dispatcher()

    def render(payload):
        calls.append(payload)
        return {"run": len(calls), "payload": payload}

    d.register("render", render)
    return d


class TestSameKeyReuse(unittest.TestCase):
    def test_same_key_returns_first_result_without_rerun(self):
        with tempfile.TemporaryDirectory() as store:
            calls = []
            sub = IdempotentSubmitter(make_dispatcher(calls), store, ttl=60)
            r1 = sub.submit("k1", "render", {"name": "a"})
            r2 = sub.submit("k1", "render", {"name": "a"})
            r3 = sub.submit("k1", "render", {"name": "a"})
            self.assertEqual(r1, r2)
            self.assertEqual(r2, r3)
            self.assertEqual(len(calls), 1)

    def test_different_keys_run_independently(self):
        with tempfile.TemporaryDirectory() as store:
            calls = []
            sub = IdempotentSubmitter(make_dispatcher(calls), store, ttl=60)
            r1 = sub.submit("k1", "render", {"name": "a"})
            r2 = sub.submit("k2", "render", {"name": "a"})
            self.assertEqual(len(calls), 2)
            self.assertNotEqual(r1["run"], r2["run"])

    def test_none_result_is_cached(self):
        with tempfile.TemporaryDirectory() as store:
            d = Dispatcher()
            calls = []
            d.register("noop", lambda p: calls.append(p) and None)
            sub = IdempotentSubmitter(d, store, ttl=60)
            self.assertIsNone(sub.submit("k1", "noop", {}))
            self.assertIsNone(sub.submit("k1", "noop", {}))
            self.assertEqual(len(calls), 1)


class TestRestartReplay(unittest.TestCase):
    def test_new_instance_replays_from_disk(self):
        with tempfile.TemporaryDirectory() as store:
            calls1 = []
            sub1 = IdempotentSubmitter(make_dispatcher(calls1), store, ttl=60)
            r1 = sub1.submit("k1", "render", {"name": "a"})
            self.assertEqual(len(calls1), 1)

            # 模拟进程重启：全新的 Dispatcher 与 Submitter，指向同一目录
            calls2 = []
            sub2 = IdempotentSubmitter(make_dispatcher(calls2), store, ttl=60)
            r2 = sub2.submit("k1", "render", {"name": "a"})
            self.assertEqual(r2, r1)
            self.assertEqual(calls2, [])  # handler 没有再次执行


class TestConcurrentSameKey(unittest.TestCase):
    def test_single_execution_under_concurrency(self):
        with tempfile.TemporaryDirectory() as store:
            d = Dispatcher()
            entered = threading.Event()
            release = threading.Event()
            calls = []

            def slow(payload):
                calls.append(payload)
                entered.set()
                assert release.wait(timeout=5)
                return {"done": payload}

            d.register("slow", slow)
            sub = IdempotentSubmitter(d, store, ttl=60)

            results = [None] * 5

            def worker(i):
                results[i] = sub.submit("k1", "slow", {"x": 1})

            threads = [threading.Thread(target=worker, args=(i,))
                       for i in range(5)]
            threads[0].start()
            assert entered.wait(timeout=5)  # 首线程已进入 handler
            for t in threads[1:]:
                t.start()  # 其余线程同键提交，应等首跑结果
            release.set()
            for t in threads:
                t.join(timeout=5)

            self.assertEqual(len(calls), 1)
            self.assertEqual(results, [{"done": {"x": 1}}] * 5)


class TestExpiry(unittest.TestCase):
    def test_expired_key_reruns(self):
        with tempfile.TemporaryDirectory() as store:
            clock = FakeClock()
            calls = []
            sub = IdempotentSubmitter(make_dispatcher(calls), store,
                                      ttl=10, clock=clock)
            r1 = sub.submit("k1", "render", {"name": "a"})
            clock.advance(11)  # 拨快时钟，越过 TTL
            r2 = sub.submit("k1", "render", {"name": "a"})
            self.assertEqual(len(calls), 2)
            self.assertEqual(r1["run"], 1)
            self.assertEqual(r2["run"], 2)

    def test_within_ttl_not_expired(self):
        with tempfile.TemporaryDirectory() as store:
            clock = FakeClock()
            calls = []
            sub = IdempotentSubmitter(make_dispatcher(calls), store,
                                      ttl=10, clock=clock)
            sub.submit("k1", "render", {"name": "a"})
            clock.advance(9)
            sub.submit("k1", "render", {"name": "a"})
            self.assertEqual(len(calls), 1)

    def test_expired_entries_lazily_swept(self):
        with tempfile.TemporaryDirectory() as store:
            clock = FakeClock()
            calls = []
            sub = IdempotentSubmitter(make_dispatcher(calls), store,
                                      ttl=10, clock=clock)
            sub.submit("k1", "render", {"name": "a"})
            sub.submit("k2", "render", {"name": "a"})
            self.assertEqual(len(os.listdir(store)), 2)
            clock.advance(11)
            sub.submit("k3", "render", {"name": "a"})  # 写时顺手清
            self.assertEqual(len(os.listdir(store)), 1)


if __name__ == "__main__":
    unittest.main()
