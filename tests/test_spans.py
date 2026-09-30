"""spanx 现有行为的锁定测试（基线，一字不改）。

全部用固定序列与逐字断言，不依赖随机输入，保证可复现。
"""

import unittest

from spanx import (
    EmptyInputError,
    InvalidInputError,
    SpanError,
    count_naive_visits,
    daily_temperatures,
    first_greater_left,
    first_greater_right,
    first_smaller_left,
    first_smaller_right,
    greater_bounds,
    histogram_bounds,
    largest_rectangle,
    min_range_lengths,
    smaller_bounds,
)

MIXED = [3, 1, 4, 1, 5, 9, 2, 6]


class TestSingleBounds(unittest.TestCase):
    def test_greater_left_on_mixed(self):
        got = [first_greater_left(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [-1, 0, -1, 2, -1, -1, 5, 5])

    def test_greater_right_on_mixed(self):
        got = [first_greater_right(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [2, 2, 4, 4, 5, -1, 7, -1])

    def test_smaller_left_on_mixed(self):
        got = [first_smaller_left(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [-1, -1, 1, -1, 3, 4, 3, 6])

    def test_smaller_right_on_mixed(self):
        got = [first_smaller_right(MIXED, i) for i in range(len(MIXED))]
        self.assertEqual(got, [1, -1, 3, -1, 6, 6, -1, -1])

    def test_strict_comparison_ignores_equals(self):
        data = [2, 2, 2]
        self.assertEqual(first_greater_left(data, 2), -1)
        self.assertEqual(first_greater_right(data, 0), -1)
        self.assertEqual(first_smaller_left(data, 2), -1)
        self.assertEqual(first_smaller_right(data, 0), -1)


class TestPairedBounds(unittest.TestCase):
    def test_greater_bounds_on_mixed(self):
        self.assertEqual(
            greater_bounds(MIXED),
            ([-1, 0, -1, 2, -1, -1, 5, 5], [2, 2, 4, 4, 5, -1, 7, -1]))

    def test_smaller_bounds_on_mixed(self):
        self.assertEqual(
            smaller_bounds(MIXED),
            ([-1, -1, 1, -1, 3, 4, 3, 6], [1, -1, 3, -1, 6, 6, -1, -1]))

    def test_greater_bounds_on_strictly_increasing(self):
        self.assertEqual(greater_bounds([1, 2, 3, 4]),
                         ([-1, -1, -1, -1], [1, 2, 3, -1]))

    def test_greater_bounds_on_strictly_decreasing(self):
        self.assertEqual(greater_bounds([4, 3, 2, 1]),
                         ([-1, 0, 1, 2], [-1, -1, -1, -1]))

    def test_bounds_on_all_equal(self):
        self.assertEqual(greater_bounds([5, 5, 5]), ([-1, -1, -1], [-1, -1, -1]))
        self.assertEqual(smaller_bounds([5, 5, 5]), ([-1, -1, -1], [-1, -1, -1]))

    def test_bounds_on_single_element(self):
        self.assertEqual(greater_bounds([7]), ([-1], [-1]))
        self.assertEqual(smaller_bounds([7]), ([-1], [-1]))

    def test_bounds_on_negative_values(self):
        self.assertEqual(greater_bounds([-2, -5, -1]),
                         ([-1, 0, -1], [2, 2, -1]))
        self.assertEqual(smaller_bounds([-2, -5, -1]),
                         ([-1, -1, 1], [1, -1, -1]))


class TestWindowDerived(unittest.TestCase):
    def test_min_range_lengths_on_mixed(self):
        self.assertEqual(min_range_lengths(MIXED), [1, 8, 1, 8, 2, 1, 4, 1])

    def test_min_range_lengths_on_all_equal(self):
        self.assertEqual(min_range_lengths([5, 5, 5]), [3, 3, 3])

    def test_min_range_lengths_on_single(self):
        self.assertEqual(min_range_lengths([7]), [1])

    def test_daily_temperatures_on_mixed(self):
        self.assertEqual(daily_temperatures(MIXED), [2, 1, 2, 1, 1, 0, 1, 0])

    def test_daily_temperatures_on_all_equal(self):
        self.assertEqual(daily_temperatures([5, 5, 5]), [0, 0, 0])

    def test_daily_temperatures_on_strictly_decreasing(self):
        self.assertEqual(daily_temperatures([5, 4, 3, 2]), [0, 0, 0, 0])


class TestHistogram(unittest.TestCase):
    def test_histogram_bounds_on_mixed(self):
        self.assertEqual(
            histogram_bounds(MIXED),
            ([-1, -1, 1, -1, 3, 4, 3, 6], [1, 8, 3, 8, 6, 6, 8, 8]))

    def test_histogram_bounds_on_all_equal(self):
        self.assertEqual(histogram_bounds([2, 2, 2, 2]),
                         ([-1, -1, -1, -1], [4, 4, 4, 4]))

    def test_histogram_bounds_on_single(self):
        self.assertEqual(histogram_bounds([7]), ([-1], [1]))

    def test_largest_rectangle_on_mixed(self):
        self.assertEqual(largest_rectangle(MIXED), 10)

    def test_largest_rectangle_on_all_equal(self):
        self.assertEqual(largest_rectangle([2, 2, 2, 2]), 8)

    def test_largest_rectangle_on_single(self):
        self.assertEqual(largest_rectangle([7]), 7)

    def test_largest_rectangle_on_negative_values(self):
        self.assertEqual(largest_rectangle([-2, -5, -1]), 0)

    def test_largest_rectangle_on_empty(self):
        self.assertEqual(largest_rectangle([]), 0)


class TestInstrumentation(unittest.TestCase):
    def test_naive_visits_on_three(self):
        self.assertEqual(count_naive_visits([1, 2, 3]), 5)

    def test_naive_visits_on_mixed(self):
        self.assertEqual(count_naive_visits(MIXED), 26)

    def test_naive_visits_on_empty(self):
        self.assertEqual(count_naive_visits([]), 0)

    def test_naive_visits_grows_with_length(self):
        small = count_naive_visits(list(range(8)))
        large = count_naive_visits(list(range(32)))
        self.assertGreater(large, small)


class TestValidation(unittest.TestCase):
    def test_non_integer_raises(self):
        with self.assertRaises(InvalidInputError):
            first_greater_left([1, "x"], 0)

    def test_bool_is_not_integer(self):
        with self.assertRaises(InvalidInputError):
            greater_bounds([True, False])

    def test_bad_index_raises(self):
        with self.assertRaises(InvalidInputError):
            first_smaller_right([1, 2], 5)

    def test_negative_index_raises(self):
        with self.assertRaises(InvalidInputError):
            first_smaller_left([1, 2], -1)

    def test_empty_query_raises(self):
        with self.assertRaises(EmptyInputError):
            smaller_bounds([])

        with self.assertRaises(EmptyInputError):
            min_range_lengths([])

    def test_errors_share_base_class(self):
        with self.assertRaises(SpanError):
            greater_bounds([1.5])

        with self.assertRaises(SpanError):
            daily_temperatures([])


if __name__ == "__main__":
    unittest.main()
