"""halfenum 现有行为的锁定测试。"""

import unittest

from halfenum import (
    HalfEnumError,
    InvalidInput,
    count_achievable_sums,
    group_difference,
    max_subset_sum,
    naive_enumeration_count,
    subset_sum_solution,
)
from halfenum.naive import iter_subsets


class TestInputValidation(unittest.TestCase):
    def test_non_integer_element_rejected(self):
        with self.assertRaises(InvalidInput):
            max_subset_sum([1, 2.5], 10)

    def test_bool_element_rejected(self):
        with self.assertRaises(InvalidInput):
            max_subset_sum([1, True], 10)

    def test_string_values_rejected(self):
        with self.assertRaises(InvalidInput):
            max_subset_sum("abc", 10)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(InvalidInput):
            max_subset_sum([1, 2], -1)

    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(InvalidInput, HalfEnumError))
        self.assertTrue(issubclass(HalfEnumError, ValueError))


class TestIterSubsets(unittest.TestCase):
    def test_empty_yields_only_empty_subset(self):
        self.assertEqual(list(iter_subsets([])), [()])

    def test_single_element(self):
        self.assertEqual(list(iter_subsets([7])), [(), (0,)])

    def test_count_matches_power_of_two(self):
        self.assertEqual(len(list(iter_subsets([1, 2, 3]))), 8)

    def test_indices_are_ascending(self):
        for indices in iter_subsets([1, 2, 3, 4]):
            self.assertEqual(list(indices), sorted(indices))


class TestEnumerationCount(unittest.TestCase):
    def test_matches_power_of_two(self):
        for n in range(6):
            self.assertEqual(naive_enumeration_count(n), 1 << n)

    def test_negative_n_rejected(self):
        with self.assertRaises(InvalidInput):
            naive_enumeration_count(-1)


class TestMaxSubsetSum(unittest.TestCase):
    def test_empty_collection(self):
        self.assertEqual(max_subset_sum([], 10), 0)

    def test_all_positive_capped_by_capacity(self):
        self.assertEqual(max_subset_sum([3, 4, 5], 7), 7)

    def test_capacity_larger_than_total(self):
        self.assertEqual(max_subset_sum([1, 2, 3], 100), 6)

    def test_all_zero(self):
        self.assertEqual(max_subset_sum([0, 0, 0], 0), 0)


class TestSubsetSumSolution(unittest.TestCase):
    def test_target_zero_on_empty(self):
        self.assertEqual(subset_sum_solution([], 0), ())

    def test_lexicographically_smallest(self):
        self.assertEqual(subset_sum_solution([1, 1, 1], 1), (0,))

    def test_unreachable_target(self):
        self.assertIsNone(subset_sum_solution([2, 4, 6], 5))

    def test_zero_elements_allow_empty_solution(self):
        self.assertEqual(subset_sum_solution([0, 3], 0), ())


class TestCountAchievableSums(unittest.TestCase):
    def test_empty_counts_zero(self):
        self.assertEqual(count_achievable_sums([]), 1)

    def test_distinct_sums(self):
        self.assertEqual(count_achievable_sums([1, 2, 3]), 7)

    def test_all_zero_collapse_to_one(self):
        self.assertEqual(count_achievable_sums([0, 0]), 1)

    def test_dedup_by_value_not_scheme(self):
        self.assertEqual(count_achievable_sums([1, 1]), 3)


class TestGroupDifference(unittest.TestCase):
    def test_min_on_balanced_pair(self):
        self.assertEqual(group_difference([3, 1], "min"), 2)

    def test_min_on_four_numbers(self):
        self.assertEqual(group_difference([1, 2, 3, 4], "min"), 0)

    def test_max_on_four_numbers(self):
        self.assertEqual(group_difference([1, 2, 3, 4], "max"), 8)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(InvalidInput):
            group_difference([1, 2], "average")


if __name__ == "__main__":
    unittest.main()
