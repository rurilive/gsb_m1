"""invx 现有朴素行为的锁定测试。

这些用例把基线的对外行为钉住：构造与规范、三类下标对计数、
重复判定与不同取值计数、按排名取值与求排名、边界与异常层级、
固定输入的可重复性。改造时本文件一个字都不许改，
新行为一律另开测试文件。
"""

import unittest

from invx.inv import (
    EmptySequenceError,
    InvalidInputError,
    InversionError,
    SequenceTooShortError,
    Values,
    count_equal_pairs,
    count_inversions,
    count_ordered_pairs,
    distinct_count,
    has_duplicates,
    kth_smallest,
    max_inversions,
    rank_of,
    total_pairs,
)


class TestInputValidation(unittest.TestCase):
    def test_empty_is_allowed(self):
        self.assertEqual(count_inversions([]), 0)

    def test_non_iterable_raises(self):
        with self.assertRaises(InvalidInputError):
            count_inversions(3)

    def test_string_raises(self):
        with self.assertRaises(InvalidInputError):
            count_inversions("123")

    def test_float_raises(self):
        with self.assertRaises(InvalidInputError):
            count_inversions([1, 2.5])

    def test_bool_is_not_integer(self):
        with self.assertRaises(InvalidInputError):
            count_inversions([1, True])

    def test_negative_int_allowed(self):
        self.assertEqual(count_inversions([-1, -2]), 1)


class TestInversionCount(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(count_inversions([]), 0)

    def test_single(self):
        self.assertEqual(count_inversions([7]), 0)

    def test_two_ascending(self):
        self.assertEqual(count_inversions([1, 2]), 0)

    def test_two_descending(self):
        self.assertEqual(count_inversions([2, 1]), 1)

    def test_sorted_ascending_has_none(self):
        self.assertEqual(count_inversions([1, 2, 3, 4, 5]), 0)

    def test_sorted_descending_has_all(self):
        self.assertEqual(count_inversions([5, 4, 3, 2, 1]), 10)

    def test_all_equal_has_none(self):
        self.assertEqual(count_inversions([3, 3, 3, 3]), 0)

    def test_mixed_with_duplicates(self):
        self.assertEqual(count_inversions([2, 4, 1, 3, 5]), 3)


class TestOrderedAndEqualCounts(unittest.TestCase):
    def test_ordered_on_descending(self):
        self.assertEqual(count_ordered_pairs([3, 2, 1]), 0)

    def test_ordered_on_ascending(self):
        self.assertEqual(count_ordered_pairs([1, 2, 3]), 3)

    def test_equal_pairs_on_mixed(self):
        self.assertEqual(count_equal_pairs([1, 2, 1, 2, 1]), 4)

    def test_classification_partitions_all_pairs(self):
        data = [3, 1, 3, 2, 1]
        self.assertEqual(
            count_inversions(data) + count_ordered_pairs(data) + count_equal_pairs(data),
            total_pairs(data),
        )

    def test_total_pairs(self):
        self.assertEqual(total_pairs([0] * 5), 10)
        self.assertEqual(total_pairs([]), 0)
        self.assertEqual(total_pairs([1]), 0)


class TestDuplicatesAndDistinct(unittest.TestCase):
    def test_no_duplicates(self):
        self.assertFalse(has_duplicates([1, 2, 3]))

    def test_has_duplicates(self):
        self.assertTrue(has_duplicates([1, 2, 1]))

    def test_empty_has_no_duplicates(self):
        self.assertFalse(has_duplicates([]))

    def test_distinct_count(self):
        self.assertEqual(distinct_count([1, 1, 2, 3, 3, 3]), 3)

    def test_distinct_count_empty(self):
        self.assertEqual(distinct_count([]), 0)


class TestRankAndSelection(unittest.TestCase):
    def test_kth_smallest(self):
        self.assertEqual(kth_smallest([9, 3, 5, 1], 1), 1)
        self.assertEqual(kth_smallest([9, 3, 5, 1], 4), 9)

    def test_kth_smallest_ignores_input_order(self):
        self.assertEqual(kth_smallest([5, 1, 4, 2, 3], 3), 3)

    def test_kth_out_of_range(self):
        with self.assertRaises(SequenceTooShortError):
            kth_smallest([1, 2], 3)

    def test_kth_on_empty(self):
        with self.assertRaises(EmptySequenceError):
            kth_smallest([], 1)

    def test_rank_of(self):
        self.assertEqual(rank_of([5, 1, 4, 2, 3], 3), 2)

    def test_rank_of_min_and_max(self):
        self.assertEqual(rank_of([5, 1, 4], 1), 0)
        self.assertEqual(rank_of([5, 1, 4], 5), 2)


class TestMaxInversions(unittest.TestCase):
    def test_small_lengths(self):
        self.assertEqual(max_inversions(0), 0)
        self.assertEqual(max_inversions(1), 0)
        self.assertEqual(max_inversions(4), 6)

    def test_negative_raises(self):
        with self.assertRaises(InvalidInputError):
            max_inversions(-1)


class TestValuesFacade(unittest.TestCase):
    def test_summary_is_stable(self):
        values = Values([2, 4, 1, 3, 5])
        summary = values.summary()
        self.assertEqual(summary["length"], 5)
        self.assertEqual(summary["inversions"], 3)
        self.assertEqual(summary["ordered"], 7)
        self.assertEqual(summary["equal"], 0)
        self.assertEqual(summary["distinct"], 5)
        self.assertFalse(summary["has_duplicates"])

    def test_to_list_returns_copy(self):
        values = Values([1, 2, 3])
        got = values.to_list()
        got.append(99)
        self.assertEqual(values.to_list(), [1, 2, 3])

    def test_delegates_match_functions(self):
        values = Values([3, 1, 3, 2, 1])
        self.assertEqual(values.count_inversions(), count_inversions([3, 1, 3, 2, 1]))
        self.assertEqual(values.count_ordered_pairs(), count_ordered_pairs([3, 1, 3, 2, 1]))
        self.assertEqual(values.count_equal_pairs(), count_equal_pairs([3, 1, 3, 2, 1]))
        self.assertEqual(values.total_pairs(), total_pairs([3, 1, 3, 2, 1]))


class TestDeterminism(unittest.TestCase):
    def test_repeated_runs_are_identical(self):
        data = [4, 2, 4, 1, 3, 2]
        first = (count_inversions(data), count_ordered_pairs(data), count_equal_pairs(data))
        second = (count_inversions(data), count_ordered_pairs(data), count_equal_pairs(data))
        self.assertEqual(first, second)

    def test_input_not_mutated(self):
        data = [3, 1, 2]
        count_inversions(data)
        distinct_count(data)
        kth_smallest(data, 1)
        self.assertEqual(data, [3, 1, 2])


class TestExceptionHierarchy(unittest.TestCase):
    def test_base_class_covers_all(self):
        for exc in (InvalidInputError, EmptySequenceError, SequenceTooShortError):
            self.assertTrue(issubclass(exc, InversionError))

    def test_catch_base_class(self):
        with self.assertRaises(InversionError):
            kth_smallest([], 1)
        with self.assertRaises(InversionError):
            count_inversions(3)
        with self.assertRaises(InversionError):
            kth_smallest([1], 2)


if __name__ == "__main__":
    unittest.main()
