"""基线测试：锁住改造前 binanswer.binanswer.BinaryAnswerKit 的现状行为。

这些断言描述的是"当前朴素实现的事实"，不是"最终应当的样子"：
  - minimize_max_segment_sum / maximize_min_segment_sum / min_eating_speed
    与 min_max_pair_gap 都是对答案区间逐个整数往上试，可行即返回，线性扫判定；
  - maximize_min_segment_sum 按恰好 k 段切，允许空段补足段数；
  - segment_plan 给出划分点，并列取字典序最小；
  - feasible 单独暴露可行性判定，candidate_bounds / sweep_bound 走候选枚举。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from binanswer.binanswer import (  # noqa: E402
    BinaryAnswerKit,
    BinErro,
    InputErro,
    UnsatErro,
    BackendErro,
)


class TestMinimizeMaxSegmentSum(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_classic_two_segments(self):
        self.assertEqual(
            self.k.minimize_max_segment_sum([7, 2, 5, 10, 8], 2), 18)

    def test_more_segments(self):
        self.assertEqual(
            self.k.minimize_max_segment_sum([7, 2, 5, 10, 8], 3), 14)

    def test_single_segment_is_total(self):
        self.assertEqual(self.k.minimize_max_segment_sum([1, 2, 3, 4], 1), 10)

    def test_every_element_own_segment(self):
        self.assertEqual(self.k.minimize_max_segment_sum([3, 1, 4], 3), 4)

    def test_zero_items_answer_zero(self):
        self.assertEqual(self.k.minimize_max_segment_sum([0, 0, 0], 2), 0)

    def test_empty_values(self):
        self.assertEqual(self.k.minimize_max_segment_sum([], 0), 0)

    def test_single_item(self):
        self.assertEqual(self.k.minimize_max_segment_sum([5], 1), 5)

    def test_all_equal(self):
        self.assertEqual(self.k.minimize_max_segment_sum([4, 4, 4, 4], 2), 8)


class TestMaximizeMinSegmentSum(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_classic(self):
        self.assertEqual(
            self.k.maximize_min_segment_sum([1, 2, 1, 2, 1], 2), 3)

    def test_three_segments_pads_with_empty(self):
        self.assertEqual(
            self.k.maximize_min_segment_sum([1, 2, 1, 2, 1], 3), 1)

    def test_pairs(self):
        self.assertEqual(self.k.maximize_min_segment_sum([5, 5], 2), 5)
        self.assertEqual(self.k.maximize_min_segment_sum([4, 4, 4, 4], 2), 8)

    def test_single_segment_is_total(self):
        self.assertEqual(self.k.maximize_min_segment_sum([1, 2, 3], 1), 6)

    def test_every_element_own_segment(self):
        self.assertEqual(self.k.maximize_min_segment_sum([3, 1, 4], 3), 1)

    def test_zero_items_answer_zero(self):
        self.assertEqual(self.k.maximize_min_segment_sum([0, 0, 0], 2), 0)


class TestMinEatingSpeed(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_classic(self):
        self.assertEqual(self.k.min_eating_speed([3, 6, 7, 11], 8), 4)

    def test_tight_hours(self):
        self.assertEqual(self.k.min_eating_speed([30, 11, 23, 4, 20], 5), 30)

    def test_loose_hours(self):
        self.assertEqual(self.k.min_eating_speed([30, 11, 23, 4, 20], 6), 23)

    def test_single_pile(self):
        self.assertEqual(self.k.min_eating_speed([7], 1), 7)

    def test_empty_piles_floor_is_one(self):
        self.assertEqual(self.k.min_eating_speed([], 3), 1)


class TestMinMaxPairGap(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_classic(self):
        self.assertEqual(self.k.min_max_pair_gap([1, 5, 3, 19]), 2)

    def test_another(self):
        self.assertEqual(self.k.min_max_pair_gap([10, 2, 8, 3]), 1)

    def test_two_items(self):
        self.assertEqual(self.k.min_max_pair_gap([4, 9]), 5)

    def test_negative_items(self):
        self.assertEqual(self.k.min_max_pair_gap([-3, -1, -2, 5]), 1)

    def test_too_short_is_unsat(self):
        with self.assertRaises(UnsatErro):
            self.k.min_max_pair_gap([5])
        with self.assertRaises(UnsatErro):
            self.k.min_max_pair_gap([])


class TestSegmentPlan(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_plan_points(self):
        self.assertEqual(self.k.segment_plan([7, 2, 5, 10, 8], 2), [2, 4])

    def test_plan_single_segment(self):
        self.assertEqual(self.k.segment_plan([1, 2, 3], 1), [2])

    def test_plan_every_item(self):
        self.assertEqual(self.k.segment_plan([3, 1, 4], 3), [0, 1, 2])

    def test_plan_zero_items(self):
        self.assertEqual(self.k.segment_plan([0, 0, 0], 2), [0, 2])

    def test_plan_empty(self):
        self.assertEqual(self.k.segment_plan([], 0), [])


class TestFeasibleAndSweep(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_feasible_true_and_false(self):
        self.assertTrue(self.k.feasible([7, 2, 5, 10, 8], 2, 18))
        self.assertFalse(self.k.feasible([7, 2, 5, 10, 8], 2, 17))

    def test_candidate_bounds_sorted_unique(self):
        self.assertEqual(self.k.candidate_bounds([1, 3, 1, 2]), [1, 2, 3])

    def test_sweep_first_feasible(self):
        self.assertEqual(
            self.k.sweep_bound([7, 2, 5, 10, 8], 2, [2, 5, 7, 8, 10, 18]), 18)

    def test_sweep_unsat(self):
        with self.assertRaises(UnsatErro):
            self.k.sweep_bound([7, 2, 5, 10, 8], 2, [2, 5, 7])


class TestErrorsAndBoundaries(unittest.TestCase):
    def setUp(self):
        self.k = BinaryAnswerKit()

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(InputErro, BinErro))
        self.assertTrue(issubclass(UnsatErro, BinErro))
        self.assertTrue(issubclass(BackendErro, BinErro))
        self.assertTrue(issubclass(BinErro, Exception))

    def test_segments_exceed_items(self):
        with self.assertRaises(InputErro):
            self.k.minimize_max_segment_sum([1, 2], 3)

    def test_bool_is_not_int(self):
        with self.assertRaises(InputErro):
            self.k.minimize_max_segment_sum([1, True], 1)

    def test_non_int_items(self):
        with self.assertRaises(InputErro):
            self.k.minimize_max_segment_sum([1, "2"], 1)

    def test_non_sequence(self):
        with self.assertRaises(InputErro):
            self.k.minimize_max_segment_sum(5, 1)

    def test_negative_answer_minimize_unsat(self):
        with self.assertRaises(UnsatErro):
            self.k.minimize_max_segment_sum([-3, -1, -2], 2)

    def test_negative_feasible_and_speed(self):
        self.assertTrue(self.k.feasible([-3, -1, -2], 2, -3))
        self.assertEqual(self.k.min_eating_speed([-3, -1], 2), 1)


class TestCountersAndDeterminism(unittest.TestCase):
    def test_counters_grow_with_work(self):
        k = BinaryAnswerKit()
        k.minimize_max_segment_sum([7, 2, 5, 10, 8], 2)
        self.assertGreater(k.trials, 0)
        self.assertGreater(k.checks, 0)
        self.assertGreater(k.ops, 0)

    def test_reset_counters_zeroes(self):
        k = BinaryAnswerKit()
        k.minimize_max_segment_sum([7, 2, 5, 10, 8], 2)
        k.reset_counters()
        self.assertEqual((k.trials, k.checks, k.ops), (0, 0, 0))

    def test_repeat_is_deterministic(self):
        k = BinaryAnswerKit()
        first = k.segment_plan([7, 2, 5, 10, 8], 2)
        second = k.segment_plan([7, 2, 5, 10, 8], 2)
        self.assertEqual(first, second)

    def test_module_level_helpers(self):
        from binanswer import binanswer as mod
        self.assertEqual(
            mod.solve_minimize_max_segment_sum([7, 2, 5, 10, 8], 2), 18)
        self.assertEqual(
            mod.solve_maximize_min_segment_sum([1, 2, 1, 2, 1], 2), 3)
        self.assertEqual(mod.solve_min_eating_speed([3, 6, 7, 11], 8), 4)
        self.assertEqual(mod.solve_min_max_pair_gap([1, 5, 3, 19]), 2)


if __name__ == "__main__":
    unittest.main()
