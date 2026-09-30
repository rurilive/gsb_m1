"""WindowDP 现有朴素行为的锁定测试。

这份基线在改造前后都必须全绿，一个字都不许改动。
"""

import unittest

from mqdp.tables import (
    CoefErro,
    DataErro,
    MAX_POLICY,
    MIN_POLICY,
    MqdpErro,
    WindowDP,
    WindowErro,
)


class TestWindowDPBaseline(unittest.TestCase):
    def test_default_attributes(self):
        planner = WindowDP(4)
        self.assertEqual(planner.window, 4)
        self.assertEqual(planner.coef, 1)
        self.assertEqual(planner.policy, MIN_POLICY)

    def test_forward_matches_expected_table(self):
        planner = WindowDP(3, 1)
        self.assertEqual(
            planner.forward([3, 1, 4, 1, 5, 9, 2, 6]),
            [0, 3, 1, 4, 2, 6, 11, 4, 10],
        )

    def test_independent_window_scan_agrees_with_forward(self):
        planner = WindowDP(3, 1)
        values = [3, 1, 4, 1, 5, 9, 2, 6]
        self.assertEqual(planner.window_scan(values), planner.forward(values))

    def test_matches_reports_pairwise_agreement(self):
        planner = WindowDP(3, 1)
        self.assertTrue(planner.matches([3, 1, 4, 1, 5, 9, 2, 6]))
        self.assertTrue(planner.matches([]))

    def test_steps_pick_the_smallest_tied_predecessor(self):
        planner = WindowDP(3, 1)
        self.assertEqual(
            planner.steps([3, 1, 4, 1, 5, 9, 2, 6]),
            [0, 0, 0, 0, 2, 2, 4, 4, 7],
        )

    def test_max_policy_takes_the_largest_predecessor(self):
        planner = WindowDP(3, 1, MAX_POLICY)
        self.assertEqual(
            planner.forward([3, 1, 4, 1, 5, 9, 2, 6]),
            [0, 3, 4, 8, 9, 14, 23, 25, 31],
        )

    def test_window_one_reduces_to_running_prefix_sums(self):
        planner = WindowDP(1, 1)
        self.assertEqual(planner.forward([2, 5, 1, 4, 3]), [0, 2, 7, 8, 12, 15])

    def test_window_larger_than_sequence_still_runs(self):
        planner = WindowDP(10, 1)
        self.assertEqual(planner.forward([1, 2, 3]), [0, 1, 2, 3])

    def test_empty_sequence_yields_zero_table(self):
        planner = WindowDP(2, 1)
        self.assertEqual(planner.forward([]), [0])
        self.assertEqual(planner.answer([]), 0)
        self.assertEqual(planner.steps([]), [0])
        self.assertEqual(planner.window_scan([]), [0])

    def test_all_equal_sequence(self):
        planner = WindowDP(3, 1)
        self.assertEqual(planner.forward([4, 4, 4, 4, 4]), [0, 4, 4, 4, 8, 8])

    def test_negative_values_with_max_policy(self):
        planner = WindowDP(3, 2, MAX_POLICY)
        self.assertEqual(planner.forward([-1, -2, -3, -4]), [0, -2, -4, -6, -10])

    def test_tie_keeps_the_smaller_predecessor_index(self):
        planner = WindowDP(2, 1)
        self.assertEqual(planner.forward([0, 0, 0]), [0, 0, 0, 0])
        self.assertEqual(planner.steps([0, 0, 0]), [0, 0, 0, 1])

    def test_coef_scales_the_current_term(self):
        planner = WindowDP(2, 3)
        self.assertEqual(planner.forward([2, 5, 1, 4, 3]), [0, 6, 15, 9, 21, 18])

    def test_coef_can_be_overridden_per_call(self):
        planner = WindowDP(3, 1)
        self.assertEqual(planner.forward([3, 1, 4, 1, 5], coef=2), [0, 6, 2, 8, 4, 12])

    def test_policy_can_be_overridden_per_call(self):
        planner = WindowDP(3, 2)
        self.assertEqual(
            planner.forward([3, 1, 4, 1, 5], policy=MAX_POLICY),
            [0, 6, 8, 16, 18, 28],
        )

    def test_answer_is_the_last_prefix_value(self):
        planner = WindowDP(3, 1)
        self.assertEqual(planner.answer([3, 1, 4, 1, 5, 9, 2, 6]), 10)

    def test_window_equals_sequence_length(self):
        planner = WindowDP(3, 1)
        self.assertEqual(planner.forward([5, 2, 8, 1, 9]), [0, 5, 2, 8, 3, 11])
        self.assertEqual(planner.steps([5, 2, 8, 1, 9]), [0, 0, 0, 0, 2, 2])

    def test_compare_count_counts_every_predecessor(self):
        planner = WindowDP(3)
        self.assertEqual(planner.compare_count(7), 21)
        self.assertEqual(planner.compare_count(1), 0)
        self.assertEqual(planner.compare_count(0), 0)

    def test_window_must_be_positive(self):
        with self.assertRaises(WindowErro):
            WindowDP(0)
        with self.assertRaises(WindowErro):
            WindowDP(-2)

    def test_window_must_be_an_integer(self):
        with self.assertRaises(WindowErro):
            WindowDP(2.5)
        with self.assertRaises(WindowErro):
            WindowDP("3")

    def test_coef_must_be_an_integer(self):
        with self.assertRaises(CoefErro):
            WindowDP(2, 1.5)

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(MqdpErro):
            WindowDP(2, 1, "median")

    def test_non_sequence_input_is_rejected(self):
        planner = WindowDP(2, 1)
        with self.assertRaises(DataErro):
            planner.forward(42)

    def test_non_integer_terms_are_rejected(self):
        planner = WindowDP(2, 1)
        with self.assertRaises(DataErro):
            planner.forward([1, 2.5, 3])
        with self.assertRaises(DataErro):
            planner.forward([1, True, 3])

    def test_compare_count_rejects_bad_size(self):
        planner = WindowDP(2)
        with self.assertRaises(CoefErro):
            planner.compare_count(-1)
        with self.assertRaises(CoefErro):
            planner.compare_count(2.5)

    def test_errors_share_one_base(self):
        self.assertTrue(issubclass(WindowErro, MqdpErro))
        self.assertTrue(issubclass(CoefErro, MqdpErro))
        self.assertTrue(issubclass(DataErro, MqdpErro))
        self.assertTrue(issubclass(MqdpErro, ValueError))

    def test_accepts_any_iterable(self):
        planner = WindowDP(2, 1)
        self.assertEqual(planner.forward(range(4)), [0, 0, 1, 2, 4])
        self.assertEqual(planner.forward((10, 4, 8)), [0, 10, 4, 12])

    def test_repeated_runs_are_identical(self):
        planner = WindowDP(3, 1)
        values = [5, 2, 8, 2, 9, 1, 7]
        self.assertEqual(planner.forward(values), planner.forward(values))
        self.assertEqual(planner.steps(values), planner.steps(values))

    def test_results_are_fresh_lists(self):
        planner = WindowDP(2, 1)
        out = planner.forward([1, 2, 3])
        out.append(99)
        self.assertEqual(planner.forward([1, 2, 3]), [0, 1, 2, 4])


if __name__ == "__main__":
    unittest.main()
