"""基线行为测试：锁住朴素区间查询工具的四项能力。

这些测试断言的是改造前的现状：查询靠整段取出排序或逐个扫描，结果正确，
只额外暴露比较次数。基线一字不改，必须原样全绿。
"""

import unittest

from waveletx.naive import (
    InvalidRangeError,
    KthOutOfRangeError,
    NaiveRangeIndex,
    WaveletXError,
    count_equal,
    count_leq,
    kth_smallest,
    range_rank,
)


SAMPLE = [5, 1, 4, 1, 9, 2, 6, 3]


class PlainFunctionTest(unittest.TestCase):
    def test_kth_smallest_first(self):
        self.assertEqual(kth_smallest(SAMPLE, 1, 7, 0), 1)

    def test_kth_smallest_middle_and_last(self):
        self.assertEqual(kth_smallest(SAMPLE, 1, 7, 2), 2)
        self.assertEqual(kth_smallest(SAMPLE, 1, 7, 5), 9)

    def test_kth_smallest_full_range(self):
        self.assertEqual(kth_smallest(SAMPLE, 0, 8, 7), 9)

    def test_range_rank(self):
        self.assertEqual(range_rank(SAMPLE, 0, 8, 4), 4)

    def test_count_leq(self):
        self.assertEqual(count_leq(SAMPLE, 2, 6, 4), 3)

    def test_count_equal(self):
        self.assertEqual(count_equal(SAMPLE, 0, 8, 1), 2)

    def test_count_equal_absent(self):
        self.assertEqual(count_equal(SAMPLE, 0, 8, 100), 0)

    def test_all_same_values(self):
        same = [7, 7, 7, 7]
        self.assertEqual(kth_smallest(same, 0, 4, 2), 7)
        self.assertEqual(range_rank(same, 0, 4, 7), 0)
        self.assertEqual(count_equal(same, 0, 4, 7), 4)

    def test_negative_values(self):
        neg = [-3, 0, -1, 2]
        self.assertEqual(kth_smallest(neg, 0, 4, 0), -3)
        self.assertEqual(count_leq(neg, 0, 4, -1), 2)
        self.assertEqual(range_rank(neg, 0, 4, 0), 2)

    def test_empty_array(self):
        self.assertEqual(count_equal([], 0, 0, 5), 0)
        self.assertEqual(count_leq([], 0, 0, 5), 0)
        self.assertEqual(range_rank([], 0, 0, 5), 0)


class RangeValidationTest(unittest.TestCase):
    def test_invalid_range_rejected(self):
        with self.assertRaises(InvalidRangeError):
            kth_smallest(SAMPLE, 3, 2, 0)

    def test_range_exceeds_size(self):
        with self.assertRaises(InvalidRangeError):
            count_leq(SAMPLE, 0, 9, 3)

    def test_negative_endpoint(self):
        with self.assertRaises(InvalidRangeError):
            range_rank(SAMPLE, -1, 3, 3)

    def test_non_integer_endpoint(self):
        with self.assertRaises(InvalidRangeError):
            count_equal(SAMPLE, 0, 1.5, 3)

    def test_k_out_of_range(self):
        with self.assertRaises(KthOutOfRangeError):
            kth_smallest(SAMPLE, 0, 3, 3)

    def test_negative_k(self):
        with self.assertRaises(KthOutOfRangeError):
            kth_smallest(SAMPLE, 0, 3, -1)

    def test_k_on_empty_segment(self):
        with self.assertRaises(KthOutOfRangeError):
            kth_smallest(SAMPLE, 2, 2, 0)

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(InvalidRangeError, WaveletXError))
        self.assertTrue(issubclass(KthOutOfRangeError, WaveletXError))


class NaiveIndexTest(unittest.TestCase):
    def test_results_match_plain_functions(self):
        index = NaiveRangeIndex(SAMPLE)
        self.assertEqual(index.kth_smallest(1, 7, 2),
                         kth_smallest(SAMPLE, 1, 7, 2))
        self.assertEqual(index.range_rank(0, 8, 4),
                         range_rank(SAMPLE, 0, 8, 4))
        self.assertEqual(index.count_leq(2, 6, 4),
                         count_leq(SAMPLE, 2, 6, 4))
        self.assertEqual(index.count_equal(0, 8, 1),
                         count_equal(SAMPLE, 0, 8, 1))

    def test_values_returns_a_copy(self):
        index = NaiveRangeIndex(SAMPLE)
        snapshot = index.values()
        snapshot.append(123)
        self.assertEqual(len(index), len(SAMPLE))

    def test_comparison_count_accumulates_and_resets(self):
        index = NaiveRangeIndex(SAMPLE)
        index.count_equal(0, 8, 1)
        first = index.comparison_count()
        self.assertEqual(first, 8)
        index.count_equal(0, 8, 1)
        self.assertEqual(index.comparison_count(), 2 * first)
        index.reset_comparisons()
        self.assertEqual(index.comparison_count(), 0)

    def test_longer_segment_costs_more(self):
        index = NaiveRangeIndex(SAMPLE)
        index.count_equal(0, 1, 5)
        short = index.comparison_count()
        index.reset_comparisons()
        index.count_equal(0, 8, 5)
        long = index.comparison_count()
        self.assertLess(short, long)

    def test_index_isolated_from_input_list(self):
        source = list(SAMPLE)
        index = NaiveRangeIndex(source)
        source.append(999)
        self.assertEqual(len(index), len(SAMPLE))


if __name__ == "__main__":
    unittest.main()
