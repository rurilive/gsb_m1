"""NaiveRadix 现有行为的锁定测试（朴素实现口径）。"""

import unittest

from radixlab.radix import MAX_VALUE, NaiveRadix, RadixError, RadixInputError


def loaded(values):
    r = NaiveRadix()
    r.load(values)
    return r


class TestLoad(unittest.TestCase):
    def test_values_is_copy(self):
        r = loaded([3, 1, 2])
        self.assertEqual(r.values(), [3, 1, 2])

    def test_input_not_mutated(self):
        data = [3, 1, 2]
        r = NaiveRadix()
        r.load(data)
        r.lowdigit_path()
        self.assertEqual(data, [3, 1, 2])

    def test_non_list_rejected(self):
        r = NaiveRadix()
        with self.assertRaises(RadixInputError):
            r.load("123")

    def test_negative_rejected(self):
        r = NaiveRadix()
        with self.assertRaises(RadixInputError):
            r.load([1, -2, 3])

    def test_over_max_rejected(self):
        r = NaiveRadix()
        with self.assertRaises(RadixInputError):
            r.load([1, MAX_VALUE + 1])

    def test_use_before_load_raises(self):
        r = NaiveRadix()
        with self.assertRaises(RadixInputError):
            r.comparison_sorted()


class TestWidth(unittest.TestCase):
    def test_decimal_width(self):
        self.assertEqual(loaded([0, 7, 42, 1234]).width(), 4)

    def test_binary_width(self):
        self.assertEqual(loaded([0, 1, 2, 3, 4]).bit_width(), 3)

    def test_half_width(self):
        self.assertEqual(loaded([0, 1, 2, 3, 4]).half_width(), 2)

    def test_empty_width_is_one(self):
        self.assertEqual(loaded([]).width(), 1)
        self.assertEqual(loaded([]).bit_width(), 1)


class TestSorting(unittest.TestCase):
    def test_comparison_sorted(self):
        self.assertEqual(loaded([5, 3, 8, 1, 9, 2]).comparison_sorted(),
                         [1, 2, 3, 5, 8, 9])

    def test_lowdigit_path_is_non_decreasing(self):
        r = loaded([170, 45, 75, 90, 802, 24, 2, 66])
        out = r.lowdigit_path()
        self.assertEqual(out, sorted([170, 45, 75, 90, 802, 24, 2, 66]))

    def test_lowdigit_path_matches_comparison(self):
        data = [170, 45, 75, 90, 802, 24, 2, 66]
        r = loaded(data)
        self.assertEqual(r.lowdigit_path(), r.comparison_sorted())

    def test_highdigit_path_matches_lowdigit(self):
        data = [170, 45, 75, 90, 802, 24, 2, 66]
        r = loaded(data)
        self.assertEqual(r.highdigit_path(), r.lowdigit_path())

    def test_mixed_widths_short_numbers(self):
        data = [1, 100, 10, 1000, 0]
        r = loaded(data)
        self.assertEqual(r.lowdigit_path(), [0, 1, 10, 100, 1000])

    def test_larger_batch(self):
        data = [13, 4, 105, 7, 4001, 0, 99, 8]
        r = loaded(data)
        self.assertEqual(r.lowdigit_path(), sorted(data))
        self.assertEqual(r.highdigit_path(), sorted(data))


class TestBoundaries(unittest.TestCase):
    def test_empty(self):
        r = loaded([])
        self.assertEqual(r.lowdigit_path(), [])
        self.assertEqual(r.highdigit_path(), [])
        self.assertEqual(r.comparison_sorted(), [])

    def test_single(self):
        self.assertEqual(loaded([7]).lowdigit_path(), [7])
        self.assertEqual(loaded([7]).highdigit_path(), [7])

    def test_all_equal(self):
        self.assertEqual(loaded([5, 5, 5]).lowdigit_path(), [5, 5, 5])

    def test_all_zero(self):
        r = loaded([0, 0, 0])
        self.assertEqual(r.lowdigit_path(), [0, 0, 0])
        self.assertEqual(r.highdigit_path(), [0, 0, 0])

    def test_large_value(self):
        big = 10 ** 12 + 7
        self.assertEqual(loaded([big, 1, 0]).lowdigit_path(), [0, 1, big])


class TestHistogram(unittest.TestCase):
    def test_digit_histogram(self):
        r = loaded([120, 220, 320, 5])
        self.assertEqual(r.digit_histogram(1), {2: 3, 0: 1})

    def test_bucket_counts_same_as_histogram(self):
        r = loaded([120, 220, 320, 5])
        self.assertEqual(r.bucket_counts(1), r.digit_histogram(1))

    def test_modal_digit(self):
        r = loaded([120, 220, 320, 5])
        self.assertEqual(r.modal_digit(1), 2)

    def test_modal_digit_tie_takes_smaller(self):
        r = loaded([11, 22])
        self.assertEqual(r.modal_digit(1), 1)

    def test_negative_pos_rejected(self):
        r = loaded([1, 2])
        with self.assertRaises(RadixInputError):
            r.digit_histogram(-1)


class TestCounts(unittest.TestCase):
    def test_comparison_count_grows_with_sorting(self):
        r = loaded([5, 3, 8, 1])
        before = r.comparison_count()
        r.comparison_sorted()
        self.assertGreater(r.comparison_count(), before)

    def test_placement_count_grows_with_bucketing(self):
        r = loaded([5, 3, 8, 1])
        before = r.placement_count()
        r.digit_histogram(0)
        self.assertGreater(r.placement_count(), before)

    def test_reset_counts(self):
        r = loaded([5, 3, 8, 1])
        r.comparison_sorted()
        r.reset_counts()
        self.assertEqual(r.comparison_count(), 0)
        self.assertEqual(r.placement_count(), 0)


class TestPredicates(unittest.TestCase):
    def test_is_sorted(self):
        r = loaded([1, 2, 3])
        self.assertTrue(r.is_sorted([1, 2, 3]))
        self.assertFalse(r.is_sorted([3, 2, 1]))

    def test_check_sorted(self):
        self.assertTrue(loaded([1, 2, 3]).check_sorted())
        self.assertFalse(loaded([1, 3, 2]).check_sorted())


class TestErrorsAndDeterminism(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(RadixInputError, RadixError))

    def test_repeat_runs_identical(self):
        data = [170, 45, 75, 90, 802, 24, 2, 66]
        r = loaded(data)
        first = (r.lowdigit_path(), r.highdigit_path(), r.modal_digit(0))
        second = (r.lowdigit_path(), r.highdigit_path(), r.modal_digit(0))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
