"""SegmentPlanner 现有朴素行为的锁定测试。

这份基线在改造前后都必须全绿，一个字都不许改动。
"""

import unittest

from slopex.quadratic import (
    INFINITY,
    SQUARE_POLICY,
    POSITION_POLICY,
    InvalidPolicyError,
    InvalidSequenceError,
    InvalidWeightError,
    SegmentPlanner,
    SlopexError,
)


class TestSegmentPlannerBaseline(unittest.TestCase):
    def test_default_policy_is_square(self):
        planner = SegmentPlanner()
        self.assertEqual(planner.policy, SQUARE_POLICY)
        self.assertEqual(planner.coef, 2)

    def test_square_policy_best_partition(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(planner.best_partition([1, 2]), 9)
        self.assertEqual(planner.best_partition([1, 1, 1]), 9)
        self.assertEqual(planner.best_partition([2, 3, 4, 5]), 62)

    def test_square_policy_prefix_table(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(
            planner.best_partitions([4, 1, 7, 1]),
            [0, 18, 21, 72, 75],
        )

    def test_square_policy_zero_overhead_splits_everything(self):
        planner = SegmentPlanner("square", 0)
        self.assertEqual(planner.best_partition([2, 3, 4, 5]), 54)
        self.assertEqual(planner.best_partitions([2, 3, 4, 5]), [0, 4, 13, 29, 54])

    def test_square_policy_cut_points(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(planner.best_cut_points([3, 2, 4, 2, 5]), [0, 1, 2, 3, 4])
        self.assertEqual(planner.best_cut_points([1, 1, 1]), [0, 1])

    def test_position_policy_best_partition(self):
        planner = SegmentPlanner("position", 2)
        self.assertEqual(planner.best_partition([1, 2]), 5)
        self.assertEqual(planner.best_partition([2, 3, 4, 5]), 16)
        self.assertEqual(planner.best_partition([3, 2, 4, 2, 5]), 18)

    def test_position_policy_prefix_table(self):
        planner = SegmentPlanner("position", 2)
        self.assertEqual(
            planner.best_partitions([4, 1, 7, 1]),
            [0, 6, 7, 14, 15],
        )

    def test_position_policy_cut_points(self):
        planner = SegmentPlanner("position", 0)
        self.assertEqual(planner.best_cut_points([2, 3, 4, 5]), [0])
        self.assertEqual(planner.best_cut_points([1, 1, 1]), [0])

    def test_two_policies_disagree_on_same_data(self):
        values = [3, 2, 4, 2, 5]
        square = SegmentPlanner("square", 2).best_partition(values)
        position = SegmentPlanner("position", 2).best_partition(values)
        self.assertEqual(square, 68)
        self.assertEqual(position, 18)
        self.assertNotEqual(square, position)

    def test_empty_sequence_partition_is_zero(self):
        for policy in ("square", "position"):
            planner = SegmentPlanner(policy, 2)
            self.assertEqual(planner.best_partition([]), 0)
            self.assertEqual(planner.best_partitions([]), [0])
            self.assertEqual(planner.best_cut_points([]), [])

    def test_single_element_partition_is_one_segment(self):
        self.assertEqual(SegmentPlanner("square", 2).best_partition([5]), 27)
        self.assertEqual(SegmentPlanner("position", 2).best_partition([5]), 7)
        self.assertEqual(SegmentPlanner("square", 2).best_cut_points([5]), [0])

    def test_all_zero_sequence(self):
        self.assertEqual(SegmentPlanner("square", 2).best_partitions([0, 0, 0]), [0, 2, 2, 2])
        self.assertEqual(SegmentPlanner("position", 2).best_partitions([0, 0, 0]), [0, 2, 2, 2])
        self.assertEqual(SegmentPlanner("square", 0).best_partition([0, 0, 0]), 0)

    def test_all_equal_sequence(self):
        planner = SegmentPlanner("square", 0)
        self.assertEqual(planner.best_partitions([2, 2, 2, 2, 2]), [0, 4, 8, 12, 16, 20])
        self.assertEqual(planner.best_cut_points([2, 2, 2, 2, 2]), [0, 1, 2, 3, 4])

    def test_large_first_element_shapes_cuts(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(planner.best_partition([100, 1]), 10005)
        self.assertEqual(planner.best_cut_points([100, 1]), [0, 1])

    def test_zero_coef_singletons_are_cheapest(self):
        planner = SegmentPlanner("square", 0)
        values = [1, 1, 1]
        self.assertEqual(planner.best_partitions(values), [0, 1, 2, 3])
        self.assertEqual(planner.best_cut_points(values), [0, 1, 2])

    def test_segment_cost_square(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(planner.segment_cost(3, 1), 11)
        self.assertEqual(planner.segment_cost(4, 2), 18)
        self.assertEqual(planner.segment_cost(0, 3), 2)

    def test_segment_cost_position_uses_start(self):
        planner = SegmentPlanner("position", 2)
        self.assertEqual(planner.segment_cost(3, 1, 2), 11)
        self.assertEqual(planner.segment_cost(6, 3, 0), 8)
        self.assertEqual(planner.segment_cost(6, 3, 5), 38)

    def test_compare_count_is_triangular(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(planner.compare_count(0), 0)
        self.assertEqual(planner.compare_count(1), 1)
        self.assertEqual(planner.compare_count(3), 6)
        self.assertEqual(planner.compare_count(10), 55)

    def test_compare_count_rejects_bad_scale(self):
        planner = SegmentPlanner("square", 2)
        with self.assertRaises(InvalidWeightError):
            planner.compare_count(-1)
        with self.assertRaises(InvalidWeightError):
            planner.compare_count(2.5)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(InvalidPolicyError):
            SegmentPlanner("chebyshev")
        with self.assertRaises(InvalidPolicyError):
            SegmentPlanner(7)

    def test_negative_overhead_is_rejected(self):
        with self.assertRaises(InvalidWeightError):
            SegmentPlanner("square", -1)
        with self.assertRaises(InvalidWeightError):
            SegmentPlanner("square", 1.5)

    def test_non_integer_elements_are_rejected(self):
        planner = SegmentPlanner("square", 2)
        with self.assertRaises(InvalidSequenceError):
            planner.best_partition([1, 2.0, 3])
        with self.assertRaises(InvalidSequenceError):
            planner.best_partition([1, -2, 3])

    def test_non_iterable_input_is_rejected(self):
        planner = SegmentPlanner("square", 2)
        with self.assertRaises(InvalidSequenceError):
            planner.best_partition(42)
        with self.assertRaises(InvalidSequenceError):
            planner.best_partitions(None)

    def test_segment_cost_rejects_bad_arguments(self):
        planner = SegmentPlanner("square", 2)
        with self.assertRaises(InvalidWeightError):
            planner.segment_cost(-1, 1)
        with self.assertRaises(InvalidWeightError):
            planner.segment_cost(1, 0)
        with self.assertRaises(InvalidWeightError):
            planner.segment_cost(1, 1, -1)

    def test_errors_share_one_base(self):
        self.assertTrue(issubclass(InvalidPolicyError, SlopexError))
        self.assertTrue(issubclass(InvalidWeightError, SlopexError))
        self.assertTrue(issubclass(InvalidSequenceError, SlopexError))
        self.assertTrue(issubclass(SlopexError, ValueError))

    def test_accepts_any_iterable(self):
        planner = SegmentPlanner("square", 2)
        self.assertEqual(planner.best_partition(range(3)), planner.best_partition([0, 1, 2]))
        self.assertEqual(planner.best_partition((1, 2)), 9)

    def test_repeated_runs_are_identical(self):
        planner = SegmentPlanner("square", 2)
        values = [5, 2, 8, 2, 9, 1, 7]
        self.assertEqual(planner.best_partition(values), planner.best_partition(values))
        self.assertEqual(planner.best_partitions(values), planner.best_partitions(values))
        self.assertEqual(planner.best_cut_points(values), planner.best_cut_points(values))

    def test_results_are_fresh_lists(self):
        planner = SegmentPlanner("square", 2)
        out = planner.best_partitions([1, 2, 3])
        out.append(99)
        self.assertEqual(planner.best_partitions([1, 2, 3]), [0, 3, 9, 20])

    def test_repr_mentions_policy_and_coef(self):
        self.assertEqual(repr(SegmentPlanner("position", 4)), "SegmentPlanner(policy='position', coef=4)")

    def test_infinity_constant(self):
        self.assertEqual(INFINITY, float("inf"))

    def test_policy_constants(self):
        self.assertEqual(SQUARE_POLICY, "square")
        self.assertEqual(POSITION_POLICY, "position")


if __name__ == "__main__":
    unittest.main()
