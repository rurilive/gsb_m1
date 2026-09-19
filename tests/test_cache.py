"""LRUCache 现有行为的锁定测试。"""

import unittest

from cachebox.cache import LRUCache


class TestLRUCache(unittest.TestCase):
    def test_set_then_get(self):
        c = LRUCache(4)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_get_missing_returns_none_and_counts_miss(self):
        c = LRUCache(2)
        self.assertIsNone(c.get("nope"))
        self.assertEqual(c.stats()["misses"], 1)

    def test_eviction_order_is_lru(self):
        c = LRUCache(3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")          # a 变成最近使用
        c.set("d", 4)       # 应挤掉 b
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(c.get("d"), 4)

    def test_overwrite_keeps_key_and_refreshes_recency(self):
        c = LRUCache(2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 10)      # 已存在，只覆盖，不触发驱逐
        c.set("c", 3)       # 应挤掉 b
        self.assertEqual(c.get("a"), 10)
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("c"), 3)

    def test_capacity_one(self):
        c = LRUCache(1)
        c.set("a", 1)
        c.set("b", 2)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.stats()["evicted"], 1)

    def test_delete(self):
        c = LRUCache(2)
        c.set("a", 1)
        self.assertTrue(c.delete("a"))
        self.assertFalse(c.delete("a"))
        self.assertIsNone(c.get("a"))

    def test_stats_basic(self):
        c = LRUCache(2)
        c.set("a", 1)
        c.get("a")
        c.get("x")
        c.set("b", 2)
        c.set("c", 3)       # evict a
        s = c.stats()
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["evicted"], 1)

    def test_stats_returns_fresh_dict(self):
        c = LRUCache(1)
        s = c.stats()
        s["hits"] = 99
        self.assertEqual(c.stats()["hits"], 0)

    def test_clock_is_injectable(self):
        c = LRUCache(2, clock=lambda: 123.0)
        c.set("a", 1)
        self.assertEqual(c.get("a"), 1)

    def test_invalid_capacity_raises(self):
        with self.assertRaises(ValueError):
            LRUCache(0)


if __name__ == "__main__":
    unittest.main()
