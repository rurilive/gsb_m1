"""Cache 行为基线：缓存命中、回源、并发合并、失效与过期重载。"""
import threading
import time
import unittest

from sfcache import Cache


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_loader(value="v1"):
    """返回 (loader, calls)；calls 记录每次回源的 key。"""
    calls = []

    def loader(key):
        calls.append(key)
        return "%s:%s" % (value, key)

    return loader, calls


class TestCacheBasics(unittest.TestCase):
    def test_miss_loads_and_returns_value(self):
        loader, calls = make_loader()
        cache = Cache(loader, ttl=None)
        self.assertEqual(cache.get("a"), "v1:a")
        self.assertEqual(calls, ["a"])
        self.assertEqual(cache.loads, 1)

    def test_hit_within_ttl_does_not_reload(self):
        clock = FakeClock()
        loader, calls = make_loader()
        cache = Cache(loader, ttl=60, clock=clock)
        first = cache.get("a")
        clock.advance(30)
        second = cache.get("a")
        self.assertEqual(first, second)
        self.assertEqual(calls, ["a"])
        self.assertEqual(cache.loads, 1)

    def test_reload_after_ttl_expiry(self):
        clock = FakeClock()
        loader, calls = make_loader()
        cache = Cache(loader, ttl=60, clock=clock)
        cache.get("a")
        clock.advance(61)
        cache.get("a")
        self.assertEqual(calls, ["a", "a"])
        self.assertEqual(cache.loads, 2)

    def test_different_keys_load_separately(self):
        loader, calls = make_loader()
        cache = Cache(loader, ttl=None)
        self.assertEqual(cache.get("a"), "v1:a")
        self.assertEqual(cache.get("b"), "v1:b")
        self.assertEqual(sorted(calls), ["a", "b"])

    def test_invalidate_forces_reload(self):
        loader, calls = make_loader()
        cache = Cache(loader, ttl=None)
        cache.get("a")
        cache.invalidate("a")
        cache.get("a")
        self.assertEqual(calls, ["a", "a"])
        self.assertEqual(cache.loads, 2)


class TestSingleflight(unittest.TestCase):
    def test_concurrent_get_merges_into_one_load(self):
        """同一 key 上并发到达的请求，只触发一次回源。"""
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def loader(key):
            calls.append(key)
            entered.set()
            release.wait(5.0)
            return "hot-value"

        cache = Cache(loader, ttl=None)
        n = 8
        results = [None] * n

        def worker(i):
            results[i] = cache.get("hot")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        self.assertTrue(entered.wait(5.0), "回源没有被触发")
        time.sleep(0.1)  # 等其余线程都进入等待
        release.set()
        for t in threads:
            t.join(5.0)

        self.assertEqual(calls, ["hot"])
        self.assertEqual(cache.loads, 1)
        self.assertEqual(len(results), n)
        self.assertIn("hot-value", results)


if __name__ == "__main__":
    unittest.main()
