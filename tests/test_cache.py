"""基线测试：锁住 cachex.Cache 现有的最久未使用淘汰行为。"""

import unittest

from cachex import Cache, CacheError, InvalidCapacityError, InvalidKeyError


class CapacityTest(unittest.TestCase):
    def test_positive_capacity_accepted(self):
        cache = Cache(2)
        self.assertEqual(cache.capacity, 2)

    def test_zero_capacity_rejected(self):
        with self.assertRaises(InvalidCapacityError):
            Cache(0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(InvalidCapacityError):
            Cache(-3)

    def test_non_integer_capacity_rejected(self):
        with self.assertRaises(InvalidCapacityError):
            Cache("2")

    def test_capacity_errors_share_base(self):
        with self.assertRaises(CacheError):
            Cache(0)


class BasicTest(unittest.TestCase):
    def test_hit_returns_value_and_marks_hit(self):
        cache = Cache(2)
        cache.put("a", 1)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.stats()["hits"], 1)
        self.assertEqual(cache.stats()["misses"], 0)

    def test_miss_returns_none_and_marks_miss(self):
        cache = Cache(2)
        self.assertIsNone(cache.get("nope"))
        self.assertEqual(cache.stats()["misses"], 1)

    def test_overwrite_keeps_oldest_order(self):
        cache = Cache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 99)
        self.assertEqual(cache.get("a"), 99)
        self.assertEqual(cache.stats()["evicted"], 0)

    def test_empty_key_rejected(self):
        cache = Cache(2)
        with self.assertRaises(InvalidKeyError):
            cache.put("", 1)

    def test_empty_key_error_shares_base(self):
        cache = Cache(2)
        with self.assertRaises(CacheError):
            cache.put("", 1)

    def test_peek_does_not_change_order_or_stats(self):
        cache = Cache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.peek("a"), 1)
        self.assertEqual(cache.keys(), ["a", "b"])
        self.assertEqual(cache.stats()["hits"], 0)

    def test_contains_and_len(self):
        cache = Cache(2)
        cache.put("a", 1)
        self.assertIn("a", cache)
        self.assertNotIn("b", cache)
        self.assertEqual(len(cache), 1)


class EvictionTest(unittest.TestCase):
    def test_full_evicts_least_recently_used(self):
        cache = Cache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)
        self.assertIn("c", cache)
        self.assertEqual(cache.stats()["evicted"], 1)

    def test_get_promotes_and_shifts_victim(self):
        cache = Cache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)
        cache.put("c", 3)
        self.assertNotIn("b", cache)
        self.assertIn("a", cache)
        self.assertIn("c", cache)

    def test_keys_ordered_oldest_first(self):
        cache = Cache(3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.keys(), ["b", "c", "a"])


if __name__ == "__main__":
    unittest.main()
