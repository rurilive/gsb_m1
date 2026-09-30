"""基线测试：锁住 chainkit 朴素实现的现状行为，全部必须通过。

这不是新增能力的测试，只是把现有函数的结果固定下来，改造时一字不许改。
"""

import unittest

from chainkit import (
    ChainError,
    check_dims,
    feasible,
    is_feasible,
    naive_cost,
    naive_count,
    naive_max_cost,
    naive_max_optimal,
    naive_optimal,
    naive_plan_cost,
    naive_triangle,
    parse_plan,
    plan_to_string,
    whole_cost,
    whole_count,
    whole_max_cost,
    whole_max_optimal,
    whole_optimal,
)


class TestCheckDims(unittest.TestCase):
    def test_returns_matrix_count(self):
        self.assertEqual(check_dims([10, 20, 30]), 2)
        self.assertEqual(check_dims([5, 5]), 1)

    def test_too_short_raises(self):
        with self.assertRaises(ChainError):
            check_dims([10])

    def test_non_positive_raises(self):
        with self.assertRaises(ChainError):
            check_dims([10, 0, 30])
        with self.assertRaises(ChainError):
            check_dims([10, -3, 30])

    def test_non_int_raises(self):
        with self.assertRaises(ChainError):
            check_dims([10, 2.5, 30])
        with self.assertRaises(ChainError):
            check_dims([10, True, 30])


class TestFeasible(unittest.TestCase):
    def test_true_on_valid(self):
        self.assertTrue(is_feasible([10, 20, 30]))
        self.assertTrue(feasible([1, 1]))

    def test_false_on_invalid(self):
        self.assertFalse(is_feasible([10]))
        self.assertFalse(is_feasible([10, 0, 30]))
        self.assertFalse(feasible([10, -1, 5]))


class TestNaiveCost(unittest.TestCase):
    def test_single_matrix_is_zero(self):
        self.assertEqual(naive_cost([10, 20, 30, 40], 1, 1), 0)

    def test_two_matrices(self):
        self.assertEqual(naive_cost([10, 20, 30], 0, 1), 10 * 20 * 30)

    def test_three_matrices_picks_smaller(self):
        self.assertEqual(naive_cost([10, 20, 5, 15], 0, 2), 1750)

    def test_interval_bounds(self):
        dims = [30, 35, 15, 5, 10, 20, 25]
        self.assertEqual(naive_cost(dims, 2, 5), 5375)

    def test_whole_matches_interval(self):
        dims = [30, 35, 15, 5, 10, 20, 25]
        self.assertEqual(whole_cost(dims), naive_cost(dims, 0, len(dims) - 2))

    def test_out_of_range_raises(self):
        with self.assertRaises(ChainError):
            naive_cost([10, 20, 30], 0, 5)
        with self.assertRaises(ChainError):
            naive_cost([10, 20, 30], 2, 1)


class TestNaiveOptimal(unittest.TestCase):
    def test_return_shape(self):
        cost, plan = whole_optimal([10, 20, 5, 15])
        self.assertEqual(cost, 1750)
        self.assertIsInstance(plan, tuple)

    def test_tie_picks_smallest_split(self):
        dims = [1, 1, 1, 1]
        cost, plan = whole_optimal(dims)
        self.assertEqual(cost, 2)
        self.assertEqual(plan, (0, (1, 2)))

    def test_two_matrices(self):
        cost, plan = naive_optimal([2, 3, 4], 0, 1)
        self.assertEqual(cost, 24)
        self.assertEqual(plan, (0, 1))


class TestNaiveMax(unittest.TestCase):
    def test_max_two_matrices(self):
        self.assertEqual(naive_max_cost([10, 20, 30], 0, 1), 10 * 20 * 30)

    def test_max_three_matrices(self):
        self.assertEqual(naive_max_cost([10, 20, 5, 15], 0, 2), 4500)

    def test_max_optimal_shape(self):
        cost, plan = whole_max_optimal([10, 20, 5, 15])
        self.assertEqual(cost, 4500)
        self.assertEqual(plan, (0, (1, 2)))

    def test_max_tie_smallest_split(self):
        cost, plan = whole_max_optimal([1, 1, 1, 1])
        self.assertEqual(cost, 2)
        self.assertEqual(plan, (0, (1, 2)))

    def test_max_ge_min(self):
        dims = [30, 35, 15, 5, 10, 20, 25]
        self.assertGreaterEqual(whole_max_cost(dims), whole_cost(dims))


class TestNaiveCount(unittest.TestCase):
    def test_single_is_one(self):
        self.assertEqual(naive_count([10, 20, 30], 0, 0), 1)

    def test_two_is_one(self):
        self.assertEqual(whole_count([10, 20, 30]), 1)

    def test_all_equal_three(self):
        self.assertEqual(whole_count([1, 1, 1, 1]), 2)

    def test_four_count(self):
        self.assertEqual(whole_count([5, 5, 5, 5, 5]), 5)


class TestNaiveTriangle(unittest.TestCase):
    def test_degenerate(self):
        self.assertEqual(naive_triangle([1, 2]), 0)
        self.assertEqual(naive_triangle([1, 2, 3]), 6)

    def test_square(self):
        self.assertEqual(naive_triangle([1, 1, 1, 1]), 2)

    def test_pentagon(self):
        self.assertEqual(naive_triangle([1, 1, 1, 1, 1]), 3)

    def test_non_int_raises(self):
        with self.assertRaises(ChainError):
            naive_triangle([1, 2.5, 3, 4])


class TestPlanStrings(unittest.TestCase):
    def test_to_string_two(self):
        self.assertEqual(plan_to_string([10, 20, 30], (0, 1)), "(01)")

    def test_to_string_nested(self):
        self.assertEqual(plan_to_string([10, 20, 5, 15], (0, (1, 2))), "(0(12))")

    def test_to_string_single(self):
        self.assertEqual(plan_to_string([10, 20], 0), "0")

    def test_round_trip(self):
        dims = [10, 20, 5, 15]
        cost, plan = whole_optimal(dims)
        text = plan_to_string(dims, plan)
        self.assertEqual(parse_plan(dims, text), plan)

    def test_parse_ignores_space(self):
        self.assertEqual(parse_plan([10, 20, 5, 15], "( (0 1) 2 )"), ((0, 1), 2))

    def test_parse_isolated_paren_raises(self):
        with self.assertRaises(ChainError):
            parse_plan([10, 20, 5, 15], "(0 1)2")

    def test_parse_bad_char(self):
        with self.assertRaises(ChainError):
            parse_plan([10, 20, 5, 15], "(0x1)2")

    def test_parse_unbalanced(self):
        with self.assertRaises(ChainError):
            parse_plan([10, 20, 5, 15], "(012")

    def test_parse_out_of_range(self):
        with self.assertRaises(ChainError):
            parse_plan([10, 20, 5, 15], "(09)")

    def test_parse_leftover(self):
        with self.assertRaises(ChainError):
            parse_plan([10, 20, 5, 15], "(01)2)")

    def test_plan_cost_matches_optimal(self):
        dims = [30, 35, 15, 5, 10, 20, 25]
        cost, plan = whole_optimal(dims)
        self.assertEqual(naive_plan_cost(dims, plan_to_string(dims, plan)), cost)

    def test_plan_cost_suboptimal(self):
        dims = [10, 20, 5, 15]
        self.assertEqual(naive_plan_cost(dims, "((01)2)"), 1750)
        self.assertEqual(naive_plan_cost(dims, "(0(12))"), 4500)


class TestErrorBase(unittest.TestCase):
    def test_inherits_exception(self):
        self.assertTrue(issubclass(ChainError, Exception))

    def test_fields(self):
        try:
            check_dims([10, 0, 30])
        except ChainError as exc:
            self.assertEqual(exc.position, 1)
            self.assertIn("正", exc.message)
        else:
            self.fail("应当抛错")


if __name__ == "__main__":
    unittest.main()
