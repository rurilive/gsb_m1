"""基线测试：锁住 NaiveKnapsack 的现状行为。

这是改造前的基线，一字不许改，必须始终全绿。
"""

import unittest

from knapsackdp.knapsack import NaiveKnapsack, KnapsackError


class TestConstruction(unittest.TestCase):
    def test_length_counts_items(self):
        k = NaiveKnapsack([1, 2, 3], [10, 20, 30], 5)
        self.assertEqual(len(k), 3)

    def test_capacity_is_readable(self):
        k = NaiveKnapsack([1], [1], 7)
        self.assertEqual(k.capacity, 7)

    def test_weight_value_length_mismatch_rejected(self):
        with self.assertRaises(KnapsackError):
            NaiveKnapsack([1, 2], [1], 5)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(KnapsackError):
            NaiveKnapsack([1], [1], -1)

    def test_negative_weight_rejected(self):
        with self.assertRaises(KnapsackError):
            NaiveKnapsack([-1], [1], 5)

    def test_negative_value_rejected(self):
        with self.assertRaises(KnapsackError):
            NaiveKnapsack([1], [-1], 5)

    def test_non_integer_weight_rejected(self):
        for bad in (1.5, "1", None, True):
            with self.assertRaises(KnapsackError):
                NaiveKnapsack([bad], [1], 5)

    def test_non_integer_capacity_rejected(self):
        for bad in (1.5, "5", None, True):
            with self.assertRaises(KnapsackError):
                NaiveKnapsack([1], [1], bad)


class TestMaxValue(unittest.TestCase):
    def test_empty_items_gives_zero(self):
        self.assertEqual(NaiveKnapsack([], [], 10).max_value(), 0)

    def test_zero_capacity_gives_zero(self):
        self.assertEqual(NaiveKnapsack([1, 2], [5, 6], 0).max_value(), 0)

    def test_single_fitting_item(self):
        self.assertEqual(NaiveKnapsack([3], [9], 5).max_value(), 9)

    def test_single_too_heavy_item(self):
        self.assertEqual(NaiveKnapsack([9], [9], 5).max_value(), 0)

    def test_classic_instance(self):
        k = NaiveKnapsack([1, 3, 4, 5], [1, 4, 5, 7], 7)
        self.assertEqual(k.max_value(), 9)

    def test_zero_value_items_do_not_help(self):
        k = NaiveKnapsack([2, 2], [0, 0], 4)
        self.assertEqual(k.max_value(), 0)


class TestCountCombinations(unittest.TestCase):
    def test_empty_items_has_one_empty_selection(self):
        self.assertEqual(NaiveKnapsack([], [], 10).count_combinations(), 1)

    def test_all_fit_doubles_each_item(self):
        self.assertEqual(NaiveKnapsack([1, 1, 1], [1, 1, 1], 10).count_combinations(), 8)

    def test_too_heavy_never_selected(self):
        self.assertEqual(NaiveKnapsack([9], [1], 5).count_combinations(), 1)

    def test_some_overflow(self):
        # 两件重量各为三，容量为四，可行选择为空集与任取一件，共三个
        self.assertEqual(NaiveKnapsack([3, 3], [1, 1], 4).count_combinations(), 3)


class TestErrorBase(unittest.TestCase):
    def test_error_inherits_exception(self):
        self.assertTrue(issubclass(KnapsackError, Exception))

    def test_error_can_be_caught_by_base(self):
        with self.assertRaises(KnapsackError):
            NaiveKnapsack([1], [1], -5)


if __name__ == "__main__":
    unittest.main()
