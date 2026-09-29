"""基线测试：锁住 RangeArray 的现有逐项行为。

这份测试是改造前的基线，一个字都不许改，必须始终全绿。
新的线段树行为另开 tests/test_segtree.py，不要写进这里。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from segtree.range import RangeArray, SegError, IndexError as SegIndexError


class TestBasics(unittest.TestCase):
    def test_len_and_get(self):
        a = RangeArray([3, 1, 4, 1, 5])
        self.assertEqual(len(a), 5)
        self.assertEqual([a.get(i) for i in range(5)], [3, 1, 4, 1, 5])

    def test_set_returns_new_value(self):
        a = RangeArray([3, 1, 4])
        self.assertEqual(a.set(1, 9), 9)
        self.assertEqual(a.get(1), 9)
        self.assertEqual(a.to_list(), [3, 9, 4])

    def test_empty_array(self):
        a = RangeArray()
        self.assertEqual(len(a), 0)
        self.assertEqual(a.range_sum(0, 0), 0)
        self.assertIsNone(a.range_max(0, 0))


class TestRangeAdd(unittest.TestCase):
    def test_range_add_半开(self):
        a = RangeArray([0, 0, 0, 0, 0])
        a.range_add(1, 4, 5)
        self.assertEqual(a.to_list(), [0, 5, 5, 5, 0])

    def test_range_add_empty_no_effect(self):
        a = RangeArray([1, 2, 3])
        a.range_add(2, 2, 100)
        self.assertEqual(a.to_list(), [1, 2, 3])

    def test_range_add_negative(self):
        a = RangeArray([10, 10, 10])
        a.range_add(0, 3, -4)
        self.assertEqual(a.to_list(), [6, 6, 6])


class TestRangeSum(unittest.TestCase):
    def test_sum_full(self):
        a = RangeArray([3, 1, 4, 1, 5])
        self.assertEqual(a.range_sum(0, 5), 14)

    def test_sum_subrange(self):
        a = RangeArray([3, 1, 4, 1, 5])
        self.assertEqual(a.range_sum(1, 4), 6)

    def test_sum_empty_is_zero(self):
        a = RangeArray([3, 1, 4, 1, 5])
        self.assertEqual(a.range_sum(2, 2), 0)

    def test_sum_single(self):
        a = RangeArray([7, 8, 9])
        self.assertEqual(a.range_sum(1, 2), 8)

    def test_sum_matches_manual(self):
        a = RangeArray([1, 2, 3, 4, 5])
        a.range_add(0, 3, 10)
        expect = sum(a.to_list()[1:4])
        self.assertEqual(a.range_sum(1, 4), expect)


class TestRangeMax(unittest.TestCase):
    def test_max_full(self):
        a = RangeArray([3, 9, 4, 1, 5])
        self.assertEqual(a.range_max(0, 5), 9)

    def test_max_subrange(self):
        a = RangeArray([3, 9, 4, 1, 5])
        self.assertEqual(a.range_max(2, 5), 5)

    def test_max_empty_is_none(self):
        a = RangeArray([3, 9, 4])
        self.assertIsNone(a.range_max(1, 1))

    def test_max_negative_values(self):
        a = RangeArray([-5, -2, -9])
        self.assertEqual(a.range_max(0, 3), -2)


class TestErrors(unittest.TestCase):
    def test_bad_range_l_gt_r(self):
        a = RangeArray([1, 2, 3])
        with self.assertRaises(ValueError):
            a.range_sum(2, 1)

    def test_bad_range_out_of_bounds(self):
        a = RangeArray([1, 2, 3])
        with self.assertRaises(ValueError):
            a.range_add(0, 4, 1)

    def test_negative_l(self):
        a = RangeArray([1, 2, 3])
        with self.assertRaises(ValueError):
            a.range_max(-1, 2)

    def test_get_out_of_range(self):
        a = RangeArray([1, 2, 3])
        with self.assertRaises(SegIndexError):
            a.get(5)

    def test_negative_index(self):
        a = RangeArray([1, 2, 3])
        with self.assertRaises(SegIndexError):
            a.set(-1, 0)

    def test_errors_are_segerror(self):
        a = RangeArray([1, 2, 3])
        self.assertTrue(issubclass(SegIndexError, SegError))
        with self.assertRaises(ValueError):
            a.range_sum(0, 9)
        with self.assertRaises(ValueError):
            a.range_add(3, 1, 1)


class TestOpCount(unittest.TestCase):
    def test_range_op_count_grows(self):
        a = RangeArray([1, 2, 3])
        before = a.range_op_count()
        a.range_sum(0, 3)
        a.range_add(1, 2, 0)
        self.assertEqual(a.range_op_count(), before + 2)


if __name__ == "__main__":
    unittest.main()
