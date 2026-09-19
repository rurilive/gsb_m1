"""TTL 过期行为测试，全部用注入时钟精确断言。"""

import unittest

from cachebox.cache import LRUCache


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestTTL(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(1000.0)

    def test_get_before_expiry_hits(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1, ttl=60)
        self.clock.advance(59)
        self.assertEqual(c.get("a"), 1)
        self.assertEqual(c.stats()["hits"], 1)

    def test_get_after_expiry_is_miss_and_clears(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1, ttl=60)
        self.clock.advance(61)
        self.assertIsNone(c.get("a"))
        s = c.stats()
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["expired"], 1)
        self.assertEqual(s["hits"], 0)
        # 已清除，再读不再重复计 expired
        self.assertIsNone(c.get("a"))
        s = c.stats()
        self.assertEqual(s["misses"], 2)
        self.assertEqual(s["expired"], 1)

    def test_expiry_boundary_is_exact(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1, ttl=60)
        self.clock.advance(60)  # 恰好到期时刻，视为过期
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.stats()["expired"], 1)

    def test_ttl_none_never_expires(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1)
        self.clock.advance(10 ** 9)
        self.assertEqual(c.get("a"), 1)

    def test_overwrite_recomputes_ttl(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1, ttl=60)
        self.clock.advance(50)
        c.set("a", 2, ttl=60)  # 过期时刻按新 ttl 重算
        self.clock.advance(50)
        self.assertEqual(c.get("a"), 2)
        self.clock.advance(11)
        self.assertIsNone(c.get("a"))

    def test_overwrite_with_none_clears_expiry(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1, ttl=60)
        c.set("a", 2)  # ttl=None，永不过期
        self.clock.advance(10 ** 9)
        self.assertEqual(c.get("a"), 2)

    def test_purge_expired_removes_all_expired(self):
        c = LRUCache(5, clock=self.clock)
        c.set("a", 1, ttl=60)
        c.set("b", 2, ttl=60)
        c.set("c", 3, ttl=120)
        c.set("d", 4)  # 永不过期
        self.clock.advance(61)
        self.assertEqual(c.purge_expired(), 2)
        self.assertEqual(c.stats()["expired"], 2)
        self.assertIsNone(c.get("a"))
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("c"), 3)
        self.assertEqual(c.get("d"), 4)
        # 没有过期条目时返回 0，计数不变
        self.assertEqual(c.purge_expired(), 0)
        self.assertEqual(c.stats()["expired"], 2)

    def test_full_capacity_filters_expired_before_lru_eviction(self):
        c = LRUCache(2, clock=self.clock)
        c.set("old", 1, ttl=60)
        c.set("fresh", 2)  # 永不过期
        self.clock.advance(61)  # old 过期
        c.set("new", 3)  # 容量满：先清过期的 old，无需 LRU 驱逐
        self.assertIsNone(c.get("old"))
        self.assertEqual(c.get("fresh"), 2)
        self.assertEqual(c.get("new"), 3)
        s = c.stats()
        self.assertEqual(s["expired"], 1)
        self.assertEqual(s["evicted"], 0)

    def test_lru_eviction_when_nothing_expired(self):
        c = LRUCache(2, clock=self.clock)
        c.set("a", 1, ttl=600)
        c.set("b", 2, ttl=600)
        c.set("c", 3, ttl=600)  # 没有过期条目，按 LRU 挤掉 a
        self.assertIsNone(c.get("a"))
        s = c.stats()
        self.assertEqual(s["evicted"], 1)
        self.assertEqual(s["expired"], 0)

    def test_expired_counts_both_get_and_purge(self):
        c = LRUCache(4, clock=self.clock)
        c.set("a", 1, ttl=60)
        c.set("b", 2, ttl=60)
        c.set("c", 3, ttl=60)
        self.clock.advance(61)
        self.assertIsNone(c.get("a"))  # get 顺手清除，expired +1
        self.assertEqual(c.purge_expired(), 2)  # 清掉 b、c
        self.assertEqual(c.stats()["expired"], 3)


if __name__ == "__main__":
    unittest.main()
