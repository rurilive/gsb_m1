"""Knapsack 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from knapsackx.knapsack import (
    Knapsack,
    KnapsackError,
    InvalidValueError,
    NoSolutionError,
)


class TestKnapsack(unittest.TestCase):
    def test_empty_knapsack_reaches_only_zero(self):
        knap = Knapsack()
        self.assertEqual(knap.reachable_set(5), [0])
        self.assertEqual(knap.best_value(5), 0)
        self.assertEqual(knap.reachable_set(0), [0])

    def test_capacity_zero_only_zero(self):
        knap = Knapsack([(2, 3)])
        self.assertEqual(knap.reachable_set(0), [0])
        self.assertEqual(knap.best_value(0), 0)

    def test_weight_over_capacity_ignored(self):
        knap = Knapsack([(10, 100), (2, 5)])
        self.assertEqual(knap.reachable_set(3), [0, 2])
        self.assertEqual(knap.best_value(3), 5)

    def test_zero_weight_item_always_kept(self):
        knap = Knapsack([(0, 5), (3, 2)])
        self.assertEqual(knap.reachable_set(3), [0, 3])
        self.assertEqual(knap.best_value(3), 7)
        self.assertEqual(knap.plan_value(3), [(0, 0, 5), (1, 3, 2)])

    def test_all_zero_values(self):
        knap = Knapsack([(2, 0), (3, 0)])
        self.assertEqual(knap.best_value(5), 0)
        self.assertEqual(knap.plan_value(5), [])
        self.assertEqual(knap.reachable_set(5), [0, 2, 3, 5])

    def test_reachable_set_ascending_unique(self):
        knap = Knapsack([(1, 1), (4, 4), (6, 6)])
        for limit in range(0, 14):
            got = knap.reachable_set(limit)
            self.assertEqual(got, sorted(set(got)))
            self.assertEqual(got[0], 0)

    def test_best_value(self):
        knap = Knapsack([(2, 3), (3, 4), (4, 5), (5, 6)])
        self.assertEqual(knap.best_value(7), 9)

    def test_plan_value_matches_best(self):
        knap = Knapsack([(2, 3), (3, 4), (4, 5), (5, 6)])
        plan = knap.plan_value(7)
        self.assertEqual(sum(weight for _idx, weight, _val in plan), 7)
        self.assertEqual(sum(val for _idx, _weight, val in plan), 9)

    def test_exact_fit_solution(self):
        knap = Knapsack([(2, 3), (3, 4), (4, 5)])
        plan = knap.exact_fit(5)
        self.assertEqual(sum(weight for _idx, weight, _val in plan), 5)
        self.assertEqual(sum(val for _idx, _weight, val in plan), 7)

    def test_exact_fit_no_solution(self):
        knap = Knapsack([(2, 3), (3, 4), (4, 5)])
        with self.assertRaises(NoSolutionError):
            knap.exact_fit(1)

    def test_exact_fit_is_repeatable(self):
        knap = Knapsack([(2, 3), (3, 4), (4, 5)])
        self.assertEqual(knap.exact_fit(5), knap.exact_fit(5))

    def test_at_least_solution(self):
        knap = Knapsack([(3, 5), (4, 6), (5, 7)])
        plan = knap.at_least(6)
        self.assertGreaterEqual(sum(weight for _idx, weight, _val in plan), 6)
        self.assertEqual(knap.at_least(100), [])

    def test_update_count_is_deterministic(self):
        knap = Knapsack([(1, 2), (2, 3), (3, 4)])
        knap.reachable_set(30)
        first = knap.update_count()
        self.assertGreater(first, 0)
        knap.reachable_set(30)
        self.assertEqual(knap.update_count(), first)

    def test_update_count_grows_with_capacity(self):
        knap = Knapsack([(1, 2)] * 200)
        knap.reachable_set(10)
        small = knap.update_count()
        knap.reachable_set(200)
        self.assertGreater(knap.update_count(), small)
        self.assertEqual(knap.reachable_set(200)[-1], 200)

    def test_large_capacity_best_value(self):
        knap = Knapsack([(1, 2)] * 200)
        self.assertEqual(len(knap.reachable_set(200)), 201)
        self.assertEqual(knap.best_value(200), 400)

    def test_items_returns_copy(self):
        knap = Knapsack([(1, 1)])
        got = knap.items()
        got.append((9, 9))
        self.assertEqual(knap.items(), [(1, 1)])

    def test_add_is_chainable(self):
        knap = Knapsack().add((2, 3)).add((3, 4))
        self.assertEqual(knap.best_value(5), 7)

    def test_negative_capacity_rejected(self):
        knap = Knapsack([(1, 1)])
        with self.assertRaises(InvalidValueError):
            knap.reachable_set(-1)
        with self.assertRaises(InvalidValueError):
            knap.best_value(-1)

    def test_non_integer_capacity_rejected(self):
        knap = Knapsack([(1, 1)])
        with self.assertRaises(InvalidValueError):
            knap.reachable_set(2.5)

    def test_negative_weight_rejected(self):
        with self.assertRaises(InvalidValueError):
            Knapsack([(-1, 3)])

    def test_negative_value_rejected(self):
        with self.assertRaises(InvalidValueError):
            Knapsack([(2, -3)])

    def test_non_integer_weight_rejected(self):
        with self.assertRaises(InvalidValueError):
            Knapsack([(1.5, 3)])

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidValueError, KnapsackError))
        self.assertTrue(issubclass(NoSolutionError, KnapsackError))
        self.assertTrue(issubclass(KnapsackError, Exception))

    def test_instances_are_independent(self):
        left = Knapsack([(2, 3)])
        right = Knapsack([(3, 4)])
        self.assertEqual(left.best_value(3), 3)
        self.assertEqual(right.best_value(3), 4)


if __name__ == "__main__":
    unittest.main()
