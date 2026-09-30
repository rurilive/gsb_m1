"""LruCache 朴素实现的行为基线测试。

锁住现状：固定容量，容量满时按最近访问时间戳淘汰最旧的键；
取用与写入都会刷新时间戳；淘汰时线性重扫全部条目，结果正确。
"""

import unittest

from lrucache.cache import CacheError, Erro, LruCache


class TestExceptions(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(Erro, Exception))
        self.assertTrue(issubclass(CacheError, Erro))

    def test_zero_capacity_raises(self):
        with self.assertRaises(CacheError):
            LruCache(0)

    def test_negative_capacity_raises(self):
        with self.assertRaises(CacheError):
            LruCache(-1)

    def test_non_int_capacity_raises(self):
        with self.assertRaises(CacheError):
            LruCache("4")

    def test_float_capacity_raises(self):
        with self.assertRaises(CacheError):
            LruCache(2.5)

    def test_bool_capacity_raises(self):
        with self.assertRaises(CacheError):
            LruCache(True)


class TestBasics(unittest.TestCase):
    def test_get_miss_returns_none(self):
        cache = LruCache(3)
        self.assertIsNone(cache.get("a"))

    def test_put_then_get(self):
        cache = LruCache(3)
        cache.put("a", 1)
        self.assertEqual(cache.get("a"), 1)

    def test_contains_and_len(self):
        cache = LruCache(3)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertIn("a", cache)
        self.assertNotIn("c", cache)
        self.assertEqual(len(cache), 2)

    def test_keys_are_insertion_order(self):
        cache = LruCache(3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(cache.keys(), ["a", "b", "c"])

    def test_capacity_reported(self):
        self.assertEqual(LruCache(5).capacity(), 5)

    def test_snapshot_is_a_copy(self):
        cache = LruCache(3)
        cache.put("a", 1)
        snap = cache.snapshot()
        snap["a"] = 99
        self.assertEqual(cache.get("a"), 1)


class TestLruEviction(unittest.TestCase):
    def test_oldest_is_evicted_on_overflow(self):
        cache = LruCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)
        self.assertIn("c", cache)
        self.assertEqual(len(cache), 2)

    def test_get_refreshes_recency(self):
        cache = LruCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.put("c", 3)
        self.assertIn("a", cache)
        self.assertNotIn("b", cache)

    def test_put_existing_refreshes_recency_and_value(self):
        cache = LruCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)
        cache.put("c", 3)
        self.assertNotIn("b", cache)
        self.assertEqual(cache.get("a"), 10)

    def test_keys_after_eviction(self):
        cache = LruCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(sorted(cache.keys()), ["b", "c"])

    def test_eviction_count(self):
        cache = LruCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)
        self.assertEqual(cache.evictions(), 2)

    def test_eviction_count_zero_when_under_capacity(self):
        cache = LruCache(5)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.evictions(), 0)

    def test_size_never_exceeds_capacity(self):
        cache = LruCache(3)
        for i in range(20):
            cache.put(i, i * i)
            self.assertLessEqual(len(cache), 3)


class TestDeterminism(unittest.TestCase):
    def test_repeated_runs_agree(self):
        seq = [("put", "a", 1), ("put", "b", 2), ("get", "a", None),
               ("put", "c", 3), ("put", "d", 4), ("get", "c", None)]

        def once():
            cache = LruCache(2)
            for op, key, val in seq:
                if op == "put":
                    cache.put(key, val)
                else:
                    cache.get(key)
            return cache.keys(), cache.evictions(), cache.snapshot()

        self.assertEqual(once(), once())


if __name__ == "__main__":
    unittest.main()
