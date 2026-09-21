"""LRUCache 单线程行为的锁定测试：淘汰次序、计数口径、回调语义。"""

import unittest

import support  # noqa: F401  先挂 sys.path

from lruvault import LRUCache
from lruvault.stats import hit_rate


class CacheBasicsTest(unittest.TestCase):

    def test_get_put_delete_roundtrip(self):
        cache = LRUCache(capacity=4)
        cache.put("a", 1)
        self.assertEqual(cache.get("a"), 1)
        self.assertTrue(cache.contains("a"))
        self.assertIn("a", cache)
        self.assertTrue(cache.delete("a"))
        self.assertFalse(cache.delete("a"))
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.size(), 0)
        self.assertEqual(len(cache), 0)
        sentinel = object()
        self.assertIs(cache.get("nope", sentinel), sentinel)

    def test_get_moves_key_to_the_front(self):
        cache = LRUCache(capacity=4)
        for key in "abcd":
            cache.put(key, key)
        cache.get("a")
        self.assertEqual(cache.keys(), ["a", "d", "c", "b"])
        self.assertEqual(cache.snapshot(), [("a", "a"), ("d", "d"),
                                            ("c", "c"), ("b", "b")])
        self.assertEqual(cache.keys(), ["a", "d", "c", "b"])

    def test_put_overwrite_moves_key_to_the_front(self):
        cache = LRUCache(capacity=4)
        for key in "abcd":
            cache.put(key, key)
        cache.put("b", "B")
        self.assertEqual(cache.keys(), ["b", "d", "c", "a"])
        self.assertEqual(cache.get("b"), "B")

    def test_capacity_and_validation(self):
        self.assertEqual(LRUCache(capacity=3).capacity, 3)
        with self.assertRaises(ValueError):
            LRUCache(capacity=0)
        cache = LRUCache(capacity=2)
        with self.assertRaises(ValueError):
            cache.put(None, "v")
        with self.assertRaises(ValueError):
            cache.put("k", None)


class EvictionTest(unittest.TestCase):

    def test_capacity_evicts_the_least_recently_used(self):
        evicted = []
        cache = LRUCache(capacity=2, on_evict=lambda k, v: evicted.append((k, v)))
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.put("c", 3)
        cache.put("d", 4)
        self.assertEqual(evicted, [("b", 2), ("a", 1)])
        self.assertEqual(cache.keys(), ["d", "c"])
        self.assertEqual(cache.size(), 2)
        stats = cache.stats()
        self.assertEqual((stats.evictions, stats.puts, stats.live), (2, 4, 2))

    def test_callback_receives_the_value_that_was_stored(self):
        evicted = []
        cache = LRUCache(capacity=1, on_evict=lambda k, v: evicted.append((k, v)))
        cache.put("a", 1)
        cache.put("a", 2)
        cache.put("b", 3)
        self.assertEqual(evicted, [("a", 2)])

    def test_delete_does_not_fire_the_callback(self):
        evicted = []
        cache = LRUCache(capacity=2, on_evict=lambda k, v: evicted.append((k, v)))
        cache.put("a", 1)
        cache.delete("a")
        self.assertEqual(evicted, [])


class StatsTest(unittest.TestCase):

    def test_counters_and_hit_rate(self):
        cache = LRUCache(capacity=3)
        cache.put("a", 1)
        cache.put("a", 2)
        cache.get("a")
        cache.get("a")
        cache.get("nope")
        cache.delete("a")
        cache.delete("nope")
        stats = cache.stats()
        self.assertEqual((stats.hits, stats.misses, stats.puts), (2, 1, 2))
        self.assertEqual((stats.deletes, stats.evictions, stats.live), (1, 0, 0))
        self.assertAlmostEqual(cache.hit_rate(), 2 / 3)
        self.assertEqual(hit_rate(stats), 2 / 3)


if __name__ == "__main__":
    unittest.main()
