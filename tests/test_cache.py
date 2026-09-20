"""GuardCache 现有行为的锁定测试。"""

import threading
import time
import unittest

from guardcache import GuardCache, NotFound


class FakeClock:
    """手动推进的时钟。"""

    def __init__(self, start=1000.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_loader(value="v"):
    """返回 (loader, calls)；calls 记录每次回源的 key。"""
    calls = []

    def loader(key):
        calls.append(key)
        return "%s:%s" % (value, key)

    return loader, calls


class TestBasics(unittest.TestCase):
    def test_miss_loads_and_returns_value(self):
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=None)
        self.assertEqual(cache.get("a"), "v:a")
        self.assertEqual(calls, ["a"])
        self.assertEqual(cache.stats()["loads"], 1)

    def test_hit_within_ttl_does_not_reload(self):
        clock = FakeClock()
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=60, clock=clock)
        first = cache.get("a")
        clock.advance(30)
        second = cache.get("a")
        self.assertEqual(first, second)
        self.assertEqual(calls, ["a"])
        self.assertEqual(cache.stats()["loads"], 1)

    def test_reload_after_ttl_expiry(self):
        clock = FakeClock()
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=60, clock=clock)
        cache.get("a")
        clock.advance(61)
        cache.get("a")
        self.assertEqual(calls, ["a", "a"])
        self.assertEqual(cache.stats()["loads"], 2)

    def test_different_keys_load_separately(self):
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=None)
        self.assertEqual(cache.get("a"), "v:a")
        self.assertEqual(cache.get("b"), "v:b")
        self.assertEqual(sorted(calls), ["a", "b"])

    def test_invalidate_forces_reload(self):
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=None)
        cache.get("a")
        self.assertTrue(cache.invalidate("a"))
        cache.get("a")
        self.assertEqual(calls, ["a", "a"])
        self.assertEqual(cache.stats()["loads"], 2)

    def test_clock_is_injectable(self):
        loader, _ = make_loader()
        cache = GuardCache(loader, ttl=None, clock=lambda: 123.0)
        self.assertEqual(cache.get("a"), "v:a")

    def test_invalid_capacity_raises(self):
        loader, _ = make_loader()
        with self.assertRaises(ValueError):
            GuardCache(loader, capacity=0)


class TestStats(unittest.TestCase):
    def test_stats_counts(self):
        loader, _ = make_loader()
        cache = GuardCache(loader, ttl=None, capacity=8)
        cache.get("a")
        cache.get("a")
        cache.get("x")
        cache.get("y")
        s = cache.stats()
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 3)
        self.assertEqual(s["loads"], 3)

    def test_stats_keys_are_stable(self):
        loader, _ = make_loader()
        cache = GuardCache(loader, ttl=None)
        self.assertEqual(
            set(cache.stats()),
            {"hits", "misses", "loads", "evicted", "negatives"},
        )

    def test_stats_returns_fresh_dict(self):
        loader, _ = make_loader()
        cache = GuardCache(loader, ttl=None)
        s = cache.stats()
        s["hits"] = 99
        self.assertEqual(cache.stats()["hits"], 0)


class TestCapacity(unittest.TestCase):
    def test_eviction_order_is_lru(self):
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=None, capacity=3)
        for key in ("a", "b", "c"):
            cache.get(key)
        cache.get("a")          # a 变成最近使用
        cache.get("d")          # 应挤掉 b
        self.assertEqual(cache.stats()["evicted"], 1)
        self.assertEqual(cache.get("a"), "v:a")
        self.assertEqual(cache.get("d"), "v:d")
        cache.get("b")          # b 已被挤掉，需要重新回源
        self.assertEqual(calls.count("b"), 2)

    def test_capacity_one(self):
        loader, calls = make_loader()
        cache = GuardCache(loader, ttl=None, capacity=1)
        cache.get("a")
        cache.get("b")          # 挤掉 a
        self.assertEqual(cache.stats()["evicted"], 1)
        self.assertEqual(calls.count("a"), 1)
        cache.get("a")          # 重新回源
        self.assertEqual(calls.count("a"), 2)


class TestNegativeCache(unittest.TestCase):
    def _loader(self, calls):
        def loader(key):
            calls.append(key)
            raise NotFound(key)
        return loader

    def test_not_found_raises_and_counts(self):
        calls = []
        cache = GuardCache(self._loader(calls), ttl=60, capacity=8)
        with self.assertRaises(NotFound):
            cache.get("ghost")
        s = cache.stats()
        self.assertEqual(s["loads"], 1)
        self.assertEqual(s["negatives"], 1)

    def test_negative_hit_does_not_reload(self):
        calls = []
        cache = GuardCache(self._loader(calls), ttl=60, capacity=8)
        with self.assertRaises(NotFound):
            cache.get("ghost")
        with self.assertRaises(NotFound):
            cache.get("ghost")
        self.assertEqual(calls, ["ghost"])

    def test_invalidate_negative_reloads(self):
        calls = []
        cache = GuardCache(self._loader(calls), ttl=60, capacity=8)
        with self.assertRaises(NotFound):
            cache.get("ghost")
        self.assertTrue(cache.invalidate("ghost"))
        with self.assertRaises(NotFound):
            cache.get("ghost")
        self.assertEqual(calls, ["ghost", "ghost"])

    def test_missing_key_does_not_return_value(self):
        calls = []
        cache = GuardCache(self._loader(calls), ttl=60, capacity=8)
        with self.assertRaises(NotFound):
            cache.get("ghost")
        with self.assertRaises(NotFound):
            cache.get("ghost")


class TestConcurrency(unittest.TestCase):
    def test_concurrent_different_keys_each_load_once(self):
        calls = []
        lock = threading.Lock()

        def loader(key):
            with lock:
                calls.append(key)
            time.sleep(0.02)
            return "v:" + key

        cache = GuardCache(loader, ttl=None, capacity=16)
        results = [None] * 4

        def worker(i):
            results[i] = cache.get("k%d" % i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5.0)
        self.assertEqual(sorted(calls), ["k0", "k1", "k2", "k3"])
        for i in range(4):
            self.assertEqual(results[i], "v:k%d" % i)


if __name__ == "__main__":
    unittest.main()
