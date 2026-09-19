"""LRUCache TTL 行为测试，用注入时钟精确断言过期与计数。"""

import unittest

from cachebox.cache import LRUCache


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestTTL(unittest.TestCase):
    def test_get_before_expiry_hits(self):
        clock = FakeClock()
        c = LRUCache(4, clock=clock)
        c.set("a", 1, ttl=60)
        clock.advance(59)
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.stats()["hits"], 1)

    def test_get_after_expiry_is_miss_and_clears_entry(self):
        clock = FakeClock()
        c = LRUCache(4, clock=clock)
        c.set("a", 1, ttl=60)
        clock.advance(60)
        self.assertIsNone(c.get("a"))
        s = c.stats()
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["expired"], 1)
        # 已清除，不会重复计 expired
        self.assertEqual(c.purge_expired(), 0)
        self.assertEqual(c.stats()["expired"], 1)

    def test_ttl_none_never_expires(self):
        clock = FakeClock()
        c = LRUCache(4, clock=clock)
        c.set("a", 1)
        clock.advance(10 ** 9)
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.stats()["expired"], 0)

    def test_overwrite_recomputes_expiry_with_new_ttl(self):
        clock = FakeClock()
        c = LRUCache(4, clock=clock)
        c.set("a", 1, ttl=60)
        clock.advance(50)
        c.set("a", 2, ttl=60)   # 过期时刻按新 ttl 重算
        clock.advance(50)
        self.assertEqual(c.get("a"), 2)
        clock.advance(10)
        self.assertIsNone(c.get("a"))

    def test_overwrite_with_none_clears_expiry(self):
        clock = FakeClock()
        c = LRUCache(4, clock=clock)
        c.set("a", 1, ttl=60)
        c.set("a", 2)           # 覆盖为永不过期
        clock.advance(10 ** 9)
        self.assertEqual(c.get("a"), 2)
        self.assertEqual(c.stats()["expired"], 0)

    def test_purge_expired_removes_only_expired(self):
        clock = FakeClock()
        c = LRUCache(8, clock=clock)
        c.set("a", 1, ttl=10)
        c.set("b", 2, ttl=100)
        c.set("c", 3)
        clock.advance(50)
        self.assertEqual(c.purge_expired(), 1)
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(c.stats()["expired"], 1)

    def test_full_capacity_purges_expired_before_lru_eviction(self):
        clock = FakeClock()
        c = LRUCache(2, clock=clock)
        c.set("a", 1, ttl=10)
        c.set("b", 2)
        clock.advance(20)       # a 已过期
        c.set("c", 3)           # 先清掉过期的 a，无需 LRU 驱逐
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("b"), 2)
        self.assertEqual(c.get("c"), 3)
        s = c.stats()
        self.assertEqual(s["expired"], 1)
        self.assertEqual(s["evicted"], 0)

    def test_lru_eviction_when_nothing_expired(self):
        clock = FakeClock()
        c = LRUCache(2, clock=clock)
        c.set("a", 1, ttl=1000)
        c.set("b", 2)
        c.set("c", 3)           # 无过期条目，按 LRU 挤掉 a
        self.assertIsNone(c.get("a"))
        s = c.stats()
        self.assertEqual(s["evicted"], 1)
        self.assertEqual(s["expired"], 0)

    def test_expired_entry_does_not_count_as_hit(self):
        clock = FakeClock()
        c = LRUCache(4, clock=clock)
        c.set("a", 1, ttl=5)
        clock.advance(5)
        c.get("a")
        s = c.stats()
        self.assertEqual(s["hits"], 0)
        self.assertEqual(s["misses"], 1)


if __name__ == "__main__":
    unittest.main()
