"""朴素全量计数器的锁定测试。

只覆盖当前实现已经具备的能力：精确计数、累计总量、不同元素个数、
前 k 排序、重置、参数与键的校验。新增能力（有界结构、重频查询与
误差上界、小流量过滤、合并、滑动窗口、桶数校验）另开测试文件，
本文件一字不改。
"""

import unittest

from hitcount.naive import NaiveCounter


class TestAddAndEstimate(unittest.TestCase):
    def test_estimate_of_unseen_is_zero(self):
        counter = NaiveCounter()
        self.assertEqual(counter.estimate("nope"), 0)

    def test_add_default_counts_once(self):
        counter = NaiveCounter()
        counter.add("a")
        self.assertEqual(counter.estimate("a"), 1)

    def test_add_accumulates(self):
        counter = NaiveCounter()
        counter.add("a")
        counter.add("a")
        counter.add("a", 3)
        self.assertEqual(counter.estimate("a"), 5)

    def test_count_is_same_as_estimate(self):
        counter = NaiveCounter()
        counter.add("a", 4)
        self.assertEqual(counter.count("a"), counter.estimate("a"))
        self.assertEqual(counter.count("a"), 4)

    def test_total_tracks_every_count(self):
        counter = NaiveCounter()
        counter.add("a")
        counter.add("b", 2)
        counter.add("a", 4)
        self.assertEqual(counter.total(), 7)

    def test_distinct_counts_kinds(self):
        counter = NaiveCounter()
        counter.add("a", 5)
        counter.add("b")
        self.assertEqual(counter.distinct(), 2)

    def test_estimate_rejects_unseen_but_not_empty(self):
        counter = NaiveCounter()
        with self.assertRaises(ValueError):
            counter.add("")
        with self.assertRaises(ValueError):
            counter.add(123)


class TestAddValidation(unittest.TestCase):
    def test_add_rejects_zero_count(self):
        with self.assertRaises(ValueError):
            NaiveCounter().add("a", 0)

    def test_add_rejects_negative_count(self):
        with self.assertRaises(ValueError):
            NaiveCounter().add("a", -1)

    def test_add_rejects_bool_count(self):
        with self.assertRaises(ValueError):
            NaiveCounter().add("a", True)

    def test_add_rejects_non_int_count(self):
        with self.assertRaises(ValueError):
            NaiveCounter().add("a", 1.5)

    def test_add_rejects_non_str_key(self):
        with self.assertRaises(ValueError):
            NaiveCounter().add(None)


class TestTopK(unittest.TestCase):
    def test_top_k_orders_by_count(self):
        counter = NaiveCounter()
        counter.add("a", 1)
        counter.add("b", 3)
        counter.add("c", 2)
        self.assertEqual(counter.top_k(2), [("b", 3), ("c", 2)])

    def test_top_k_breaks_ties_by_key(self):
        counter = NaiveCounter()
        counter.add("z", 2)
        counter.add("a", 2)
        counter.add("m", 2)
        self.assertEqual(counter.top_k(3), [("a", 2), ("m", 2), ("z", 2)])

    def test_top_k_larger_than_distinct(self):
        counter = NaiveCounter()
        counter.add("a", 2)
        self.assertEqual(counter.top_k(10), [("a", 2)])

    def test_top_k_zero_is_empty(self):
        counter = NaiveCounter()
        counter.add("a", 2)
        self.assertEqual(counter.top_k(0), [])

    def test_top_k_rejects_negative(self):
        with self.assertRaises(ValueError):
            NaiveCounter().top_k(-1)

    def test_top_k_rejects_bool(self):
        with self.assertRaises(ValueError):
            NaiveCounter().top_k(True)


class TestReset(unittest.TestCase):
    def test_reset_clears_everything(self):
        counter = NaiveCounter()
        counter.add("a", 5)
        counter.reset()
        self.assertEqual(counter.total(), 0)
        self.assertEqual(counter.distinct(), 0)
        self.assertEqual(counter.estimate("a"), 0)
        self.assertEqual(counter.top_k(3), [])


if __name__ == "__main__":
    unittest.main()