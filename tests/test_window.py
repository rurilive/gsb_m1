"""WindowStats 现有朴素行为的锁定测试。

这份基线在改造前后都必须全绿，一个字都不许改动。
"""

import unittest

from winx.window import (
    InvalidSequenceError,
    InvalidWindowSizeError,
    WindowStats,
    WinxError,
    window_distinct,
    window_kth,
    window_max,
    window_median,
    window_min,
    window_rank,
    window_sum,
)


class TestWindowBaseline(unittest.TestCase):
    def test_maxima_over_small_sequence(self):
        stats = WindowStats(3)
        self.assertEqual(stats.maxima([1, 3, 2, 5, 4, 6]), [3, 5, 5, 6])

    def test_minima_over_small_sequence(self):
        stats = WindowStats(3)
        self.assertEqual(stats.minima([1, 3, 2, 5, 4, 6]), [1, 2, 2, 4])

    def test_medians_over_small_sequence(self):
        stats = WindowStats(3)
        self.assertEqual(stats.medians([1, 3, 2, 5, 4, 6]), [2.0, 3.0, 4.0, 5.0])

    def test_even_window_median_is_average_of_middle_two(self):
        stats = WindowStats(4)
        self.assertEqual(stats.medians([1, 2, 3, 4]), [2.5])

    def test_sums_over_small_sequence(self):
        stats = WindowStats(3)
        self.assertEqual(stats.sums([1, 3, 2, 5, 4, 6]), [6.0, 10.0, 11.0, 15.0])

    def test_distinct_counts_over_small_sequence(self):
        stats = WindowStats(3)
        self.assertEqual(stats.distinct_counts([1, 1, 2, 2, 3]), [2, 2, 2])

    def test_window_size_one_returns_input_itself(self):
        stats = WindowStats(1)
        values = [5, 1, 9, 3]
        self.assertEqual(stats.maxima(values), values)
        self.assertEqual(stats.minima(values), values)
        self.assertEqual(stats.medians(values), [5.0, 1.0, 9.0, 3.0])
        self.assertEqual(stats.sums(values), [5.0, 1.0, 9.0, 3.0])
        self.assertEqual(stats.distinct_counts(values), [1, 1, 1, 1])

    def test_window_equals_sequence_length_yields_one_window(self):
        stats = WindowStats(4)
        values = [4, 2, 7, 1]
        self.assertEqual(stats.maxima(values), [7])
        self.assertEqual(stats.minima(values), [1])
        self.assertEqual(stats.medians(values), [3.0])
        self.assertEqual(stats.sums(values), [14.0])
        self.assertEqual(stats.distinct_counts(values), [4])

    def test_window_larger_than_sequence_yields_no_windows(self):
        stats = WindowStats(5)
        values = [1, 2, 3]
        self.assertEqual(stats.maxima(values), [])
        self.assertEqual(stats.minima(values), [])
        self.assertEqual(stats.medians(values), [])
        self.assertEqual(stats.sums(values), [])
        self.assertEqual(stats.distinct_counts(values), [])

    def test_empty_sequence_yields_no_windows(self):
        stats = WindowStats(2)
        self.assertEqual(stats.maxima([]), [])
        self.assertEqual(stats.distinct_counts([]), [])

    def test_all_equal_sequence(self):
        stats = WindowStats(3)
        values = [7, 7, 7, 7, 7]
        self.assertEqual(stats.maxima(values), [7, 7, 7])
        self.assertEqual(stats.minima(values), [7, 7, 7])
        self.assertEqual(stats.distinct_counts(values), [1, 1, 1])

    def test_repeated_elements_are_kept(self):
        stats = WindowStats(2)
        values = [2, 2, 3, 2]
        self.assertEqual(stats.maxima(values), [2, 3, 3])
        self.assertEqual(stats.minima(values), [2, 2, 2])
        self.assertEqual(stats.distinct_counts(values), [1, 2, 2])

    def test_kth_smallest_is_zero_based(self):
        stats = WindowStats(3)
        values = [1, 3, 2, 5, 4]
        self.assertEqual(stats.kth_smallest(values, 0), [1, 2, 2])
        self.assertEqual(stats.kth_smallest(values, 2), [3, 5, 5])

    def test_kth_smallest_keeps_duplicates(self):
        stats = WindowStats(3)
        values = [2, 2, 2, 3, 1]
        self.assertEqual(stats.kth_smallest(values, 0), [2, 2, 1])
        self.assertEqual(stats.kth_smallest(values, 1), [2, 2, 2])

    def test_rank_counts_strictly_smaller(self):
        stats = WindowStats(3)
        values = [1, 3, 2, 5, 4]
        self.assertEqual(stats.rank(values, 3), [2, 1, 1])

    def test_rank_of_absent_value_edges(self):
        stats = WindowStats(3)
        values = [1, 3, 2]
        self.assertEqual(stats.rank(values, 0), [0])
        self.assertEqual(stats.rank(values, 99), [3])

    def test_kth_smallest_rejects_out_of_range_k(self):
        stats = WindowStats(3)
        with self.assertRaises(WinxError):
            stats.kth_smallest([1, 2, 3], 3)
        with self.assertRaises(WinxError):
            stats.kth_smallest([1, 2, 3], -1)

    def test_median_is_float_on_odd_window(self):
        stats = WindowStats(3)
        self.assertIsInstance(stats.medians([1, 2, 3])[0], float)

    def test_window_size_must_be_positive(self):
        with self.assertRaises(InvalidWindowSizeError):
            WindowStats(0)
        with self.assertRaises(InvalidWindowSizeError):
            WindowStats(-3)

    def test_window_size_must_be_integer(self):
        with self.assertRaises(InvalidWindowSizeError):
            WindowStats(2.5)
        with self.assertRaises(InvalidWindowSizeError):
            WindowStats("3")

    def test_non_sequence_input_is_rejected(self):
        stats = WindowStats(2)
        with self.assertRaises(InvalidSequenceError):
            stats.maxima(42)

    def test_errors_share_one_base(self):
        self.assertTrue(issubclass(InvalidWindowSizeError, WinxError))
        self.assertTrue(issubclass(InvalidSequenceError, WinxError))
        self.assertTrue(issubclass(WinxError, ValueError))

    def test_module_level_helpers_match_instance_methods(self):
        values = [3, 1, 4, 1, 5, 9, 2, 6]
        self.assertEqual(window_max(values, 3), WindowStats(3).maxima(values))
        self.assertEqual(window_min(values, 3), WindowStats(3).minima(values))
        self.assertEqual(window_median(values, 3), WindowStats(3).medians(values))
        self.assertEqual(window_sum(values, 3), WindowStats(3).sums(values))
        self.assertEqual(window_distinct(values, 3), WindowStats(3).distinct_counts(values))
        self.assertEqual(window_kth(values, 3, 1), WindowStats(3).kth_smallest(values, 1))
        self.assertEqual(window_rank(values, 3, 3), WindowStats(3).rank(values, 3))

    def test_accepts_any_iterable(self):
        stats = WindowStats(2)
        self.assertEqual(stats.maxima(range(5)), [1, 2, 3, 4])
        self.assertEqual(stats.maxima((10, 4, 8)), [10, 8])

    def test_repeated_runs_are_identical(self):
        stats = WindowStats(3)
        values = [5, 2, 8, 2, 9, 1, 7]
        self.assertEqual(stats.maxima(values), stats.maxima(values))
        self.assertEqual(stats.sums(values), stats.sums(values))

    def test_results_are_fresh_lists(self):
        stats = WindowStats(2)
        out = stats.maxima([1, 2, 3])
        out.append(99)
        self.assertEqual(stats.maxima([1, 2, 3]), [2, 3])

    def test_negative_values(self):
        stats = WindowStats(2)
        values = [-5, -1, -8]
        self.assertEqual(stats.maxima(values), [-1, -1])
        self.assertEqual(stats.minima(values), [-5, -8])
        self.assertEqual(stats.sums(values), [-6.0, -9.0])

    def test_sums_and_medians_are_float(self):
        stats = WindowStats(2)
        self.assertTrue(all(isinstance(v, float) for v in stats.sums([1, 2, 3])))
        self.assertTrue(all(isinstance(v, float) for v in stats.medians([1, 2, 3])))


if __name__ == "__main__":
    unittest.main()
