"""基线测试：锁住改造前 subfam.stats.SubarrayStats 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - best_sum 枚举全部子段，每段从头累加求和，取最大，并列取最短再取左端最小；
  - bounded_sum 枚举全部子段，逐段判断长度是否不超过上界，取其中和最大者；
  - at_most_sum 枚举全部子段，逐段判断和是否不超过上界，取满足条件的最大和；
  - range_extremes 枚举全部子段，逐段重新扫描段内极值，与全序列结果印证；
  - best_product 枚举全部子段，逐段重新累乘，区分含零与非零。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from subfam.stats import (  # noqa: E402
    SubarrayStats,
    StatsErro,
    SeqErro,
    ParamErro,
)


class TestBestSumBaseline(unittest.TestCase):
    def setUp(self):
        self.k = SubarrayStats()

    def _triple(self, seq):
        r = self.k.best_sum(seq)
        return (r.value, r.left, r.right)

    def test_empty(self):
        self.assertEqual(self._triple([]), (0, -1, -1))

    def test_single(self):
        self.assertEqual(self._triple([7]), (7, 0, 0))

    def test_all_increasing(self):
        self.assertEqual(self._triple([1, 2, 3, 4]), (10, 0, 3))

    def test_all_negative(self):
        self.assertEqual(self._triple([-5, -2, -9]), (-2, 1, 1))

    def test_all_zero(self):
        self.assertEqual(self._triple([0, 0]), (0, 0, 0))

    def test_classic(self):
        seq = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
        self.assertEqual(self._triple(seq), (6, 3, 6))

    def test_tie_prefers_leftmost(self):
        self.assertEqual(self._triple([5, -5, 5]), (5, 0, 0))

    def test_tie_prefers_shorter_then_leftmost(self):
        # 单元素段与更长段同和，取最短，即左端最小的一条。
        self.assertEqual(self._triple([1, 0]), (1, 0, 0))
        self.assertEqual(self._triple([2, -2, 2]), (2, 0, 0))

    def test_whole_sequence_is_optimal(self):
        self.assertEqual(self._triple([1, 2, 3]), (6, 0, 2))

    def test_scan_counts_all_element_visits(self):
        # 四元素序列：各段长度之和 4*1+3*2+2*3+1*4 = 20。
        r = self.k.best_sum([1, 2, 3, 4])
        self.assertEqual(r.scan, 20)

    def test_non_integer_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.best_sum([1, ""])

    def test_float_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.best_sum([1, 2.5, 3])

    def test_bool_is_not_int(self):
        with self.assertRaises(SeqErro):
            self.k.best_sum([1, True, 3])

    def test_non_iterable_raises(self):
        with self.assertRaises(SeqErro):
            self.k.best_sum(5)


class TestBoundedSumBaseline(unittest.TestCase):
    def setUp(self):
        self.k = SubarrayStats()

    def _triple(self, seq, bound):
        r = self.k.bounded_sum(seq, bound)
        return (r.value, r.left, r.right)

    def test_empty_sequence(self):
        self.assertEqual(self._triple([], 3), (0, -1, -1))

    def test_zero_bound_is_empty_segment(self):
        self.assertEqual(self._triple([1, 2, 3], 0), (0, -1, -1))

    def test_bound_covers_everything(self):
        self.assertEqual(self._triple([1, 2, 3, 4], 10), (10, 0, 3))

    def test_bound_two_picks_best_pair(self):
        self.assertEqual(self._triple([1, 2, 3, 4], 2), (7, 2, 3))

    def test_bound_one_picks_max_element(self):
        self.assertEqual(self._triple([3, -1, 2], 1), (3, 0, 0))

    def test_all_negative(self):
        self.assertEqual(self._triple([-3, -1, -2], 2), (-1, 1, 1))

    def test_tie_prefers_leftmost(self):
        self.assertEqual(self._triple([5, -10, 5], 2), (5, 0, 0))

    def test_scan_counts_only_in_bound_segments(self):
        # 长度不超过二：四段单元素加三段二元段，各段从零累加的步数为 4*1+3*2。
        r = self.k.bounded_sum([1, 2, 3, 4], 2)
        self.assertEqual(r.scan, 10)

    def test_negative_bound_raises(self):
        with self.assertRaises(ParamErro):
            self.k.bounded_sum([1, 2], -1)

    def test_bool_bound_raises(self):
        with self.assertRaises(ParamErro):
            self.k.bounded_sum([1, 2], True)

    def test_float_bound_raises(self):
        with self.assertRaises(ParamErro):
            self.k.bounded_sum([1, 2], 2.5)

    def test_bad_sequence_raises(self):
        with self.assertRaises(SeqErro):
            self.k.bounded_sum([1, "x"], 2)


class TestAtMostSumBaseline(unittest.TestCase):
    def setUp(self):
        self.k = SubarrayStats()

    def _triple(self, seq, bound):
        r = self.k.at_most_sum(seq, bound)
        return (r.value, r.left, r.right)

    def test_empty_sequence(self):
        self.assertEqual(self._triple([], 5), (0, -1, -1))

    def test_no_nonempty_segment_qualifies(self):
        self.assertEqual(self._triple([3, 1, 2], 0), (0, -1, -1))

    def test_picks_largest_sum_within_bound(self):
        self.assertEqual(self._triple([1, 2, 3, 4], 6), (6, 0, 2))

    def test_all_negative_under_zero_bound(self):
        self.assertEqual(self._triple([-5, -2, -9], 0), (-2, 1, 1))

    def test_zero_element_qualifies(self):
        self.assertEqual(self._triple([0, 5], 0), (0, 0, 0))

    def test_tie_prefers_shorter_then_leftmost(self):
        self.assertEqual(self._triple([3, -3, 3], 3), (3, 0, 0))

    def test_whole_sequence_is_optimal(self):
        self.assertEqual(self._triple([2, 1], 3), (3, 0, 1))

    def test_negative_bound_raises(self):
        with self.assertRaises(ParamErro):
            self.k.at_most_sum([1, 2], -2)

    def test_float_bound_raises(self):
        with self.assertRaises(ParamErro):
            self.k.at_most_sum([1, 2], 1.5)


class TestRangeExtremesBaseline(unittest.TestCase):
    def setUp(self):
        self.k = SubarrayStats()

    def test_typical(self):
        r = self.k.range_extremes([3, 1, 4, 1, 5])
        self.assertEqual((r.min_value, r.max_value), (1, 5))

    def test_all_equal(self):
        r = self.k.range_extremes([-2, -2])
        self.assertEqual((r.min_value, r.max_value), (-2, -2))

    def test_single(self):
        r = self.k.range_extremes([9])
        self.assertEqual((r.min_value, r.max_value), (9, 9))

    def test_scan_counts_full_and_per_segment(self):
        # 全序列扫描三次，再对全部段各重扫：3 + 10 = 13。
        r = self.k.range_extremes([3, 1, 4])
        self.assertEqual(r.scan, 13)

    def test_empty_raises(self):
        with self.assertRaises(SeqErro):
            self.k.range_extremes([])

    def test_float_raises(self):
        with self.assertRaises(SeqErro):
            self.k.range_extremes([1.5, 2])

    def test_bad_element_raises(self):
        with self.assertRaises(SeqErro):
            self.k.range_extremes([1, None])


class TestBestProductBaseline(unittest.TestCase):
    def setUp(self):
        self.k = SubarrayStats()

    def _quad(self, seq):
        r = self.k.best_product(seq)
        return (r.value, r.has_zero, r.left, r.right)

    def test_empty(self):
        self.assertEqual(self._quad([]), (0, True, -1, -1))

    def test_single(self):
        self.assertEqual(self._quad([7]), (7, False, 0, 0))

    def test_all_positive_tie_prefers_shorter(self):
        # 1*2*3*4 与 2*3*4 同为 24，取更短的一段，即左端为一的那条。
        self.assertEqual(self._quad([1, 2, 3, 4]), (24, False, 1, 3))

    def test_all_zero_shortest_segment(self):
        self.assertEqual(self._quad([0, 0]), (0, True, 0, 0))

    def test_zero_with_negatives(self):
        self.assertEqual(self._quad([0, -1, -2]), (2, False, 1, 2))

    def test_all_positive_whole_sequence(self):
        # 每个元素都大于一，去掉任一段都会变小，故整段唯一最优。
        self.assertEqual(self._quad([2, 3, 4]), (24, False, 0, 2))

    def test_zero_set_point(self):
        self.assertEqual(self._quad([2, 3, 0]), (6, False, 0, 1))

    def test_even_negatives_pair(self):
        self.assertEqual(self._quad([-3, -1, -2]), (3, False, 0, 1))

    def test_all_negative_tail_pair(self):
        self.assertEqual(self._quad([-1, -2, -3]), (6, False, 1, 2))

    def test_negative_then_zero_keeps_zero(self):
        self.assertEqual(self._quad([-2, 0]), (0, True, 1, 1))

    def test_single_zero(self):
        self.assertEqual(self._quad([0]), (0, True, 0, 0))

    def test_tie_prefers_shorter_then_leftmost(self):
        self.assertEqual(self._quad([1, 1]), (1, False, 0, 0))
        self.assertEqual(self._quad([2, 1]), (2, False, 0, 0))

    def test_scan_counts(self):
        # 三元素序列各段长度之和 3*1+2*2+1*3 = 10。
        r = self.k.best_product([1, 2, 3])
        self.assertEqual(r.scan, 10)

    def test_bad_sequence_raises(self):
        with self.assertRaises(SeqErro):
            self.k.best_product([1, "x"])


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        seq = [3, -1, 4, 0, 5, -9, 2, 6]
        k1 = SubarrayStats()
        k2 = SubarrayStats()
        self.assertEqual(k1.best_sum(seq), k2.best_sum(seq))
        self.assertEqual(k1.bounded_sum(seq, 3), k2.bounded_sum(seq, 3))
        self.assertEqual(k1.at_most_sum(seq, 7), k2.at_most_sum(seq, 7))
        self.assertEqual(k1.range_extremes(seq), k2.range_extremes(seq))
        self.assertEqual(k1.best_product(seq), k2.best_product(seq))

    def test_scan_resets_between_calls(self):
        k = SubarrayStats()
        seq = [1, 3, 2, 4]
        k.best_sum(seq)
        first = k.last_scan
        k.best_sum(seq)
        self.assertEqual(k.last_scan, first)

    def test_fresh_instance_has_zero_scan(self):
        self.assertEqual(SubarrayStats().last_scan, 0)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(SeqErro, StatsErro))
        self.assertTrue(issubclass(ParamErro, StatsErro))
        self.assertTrue(issubclass(StatsErro, Exception))


if __name__ == "__main__":
    unittest.main()
