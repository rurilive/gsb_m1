"""PageSimulator 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：请求页号的命中与缺失、LRU 淘汰、带写请
求的标脏、统计计数与非法容量的构造期拒绝。新增行为（LRU-K 访问历史、
脏页写回、写回缓冲合并、预取命中统计与指标口径）另建测试文件，不改动
本文件。
"""

import unittest

from pagekit.simulator import PageSimulator


class TestAccess(unittest.TestCase):
    def test_cold_access_is_miss(self):
        sim = PageSimulator(2)
        self.assertFalse(sim.access(7))

    def test_repeat_access_is_hit(self):
        sim = PageSimulator(2)
        sim.access(7)
        self.assertTrue(sim.access(7))

    def test_miss_installs_page(self):
        sim = PageSimulator(3)
        sim.access(7)
        self.assertIn(7, sim)
        self.assertEqual(len(sim), 1)

    def test_hit_does_not_change_size(self):
        sim = PageSimulator(3)
        sim.access(1)
        sim.access(1)
        self.assertEqual(len(sim), 1)


class TestEviction(unittest.TestCase):
    def test_evicts_least_recently_used(self):
        sim = PageSimulator(2)
        sim.access(1)
        sim.access(2)
        sim.access(1)  # 1 变最新，2 最久未用
        sim.access(3)  # 容量满，淘汰 2
        self.assertIn(1, sim)
        self.assertNotIn(2, sim)
        self.assertIn(3, sim)

    def test_single_capacity_always_evicts(self):
        sim = PageSimulator(1)
        sim.access(1)
        sim.access(2)
        self.assertNotIn(1, sim)
        self.assertIn(2, sim)
        self.assertEqual(sim.stats()["evicted"], 1)


class TestWrite(unittest.TestCase):
    def test_write_miss_installs_and_marks_dirty(self):
        sim = PageSimulator(2)
        self.assertFalse(sim.write(4))
        self.assertIn(4, sim)
        self.assertTrue(sim._frames[4]["dirty"])

    def test_write_hit_marks_dirty(self):
        sim = PageSimulator(2)
        sim.access(4)
        self.assertFalse(sim._frames[4]["dirty"])
        sim.write(4)
        self.assertTrue(sim._frames[4]["dirty"])

    def test_write_counts_hit_and_miss(self):
        sim = PageSimulator(2)
        sim.write(4)  # 缺失
        sim.write(4)  # 命中
        s = sim.stats()
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["hits"], 1)


class TestStats(unittest.TestCase):
    def test_counters(self):
        sim = PageSimulator(2)
        sim.access(1)
        sim.access(1)
        sim.access(9)
        s = sim.stats()
        self.assertEqual(s["capacity"], 2)
        self.assertEqual(s["resident"], 2)
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 2)
        self.assertEqual(s["evicted"], 0)

    def test_hit_ratio(self):
        sim = PageSimulator(4)
        sim.access(1)
        sim.access(1)
        sim.access(1)
        sim.access(1)
        self.assertAlmostEqual(sim.hit_ratio(), 0.75)

    def test_hit_ratio_empty(self):
        self.assertEqual(PageSimulator(2).hit_ratio(), 0.0)

    def test_resident_order(self):
        sim = PageSimulator(3)
        sim.access(1)
        sim.access(2)
        sim.access(1)
        self.assertEqual(sim.resident(), [2, 1])


class TestCapacityGuard(unittest.TestCase):
    def test_zero_capacity_rejected(self):
        with self.assertRaises(ValueError):
            PageSimulator(0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(ValueError):
            PageSimulator(-3)


if __name__ == "__main__":
    unittest.main()
