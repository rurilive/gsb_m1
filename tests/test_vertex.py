"""vertex 现有行为的锁定测试：输入校验、两两求交、朴素枚举求解、可行判定、
目标值、覆盖变量与组合量级的候选对数。

只覆盖当前朴素实现已经给出的结果，后面新增的单纯形法、分数精确顶点枚举、
对偶与紧约束检验、退化情形与规模对照另开文件。
"""

import unittest
from fractions import Fraction

from simplexlp import (
    EPS,
    LinearProgramError,
    all_constraint_pairs,
    as_fraction,
    naive_covered_variables,
    naive_is_feasible,
    naive_maximize,
    naive_objective_value,
    naive_optimize,
    naive_status,
    naive_vertex_count,
    point_value,
    refine_intersection,
    to_fraction,
    variables_seen,
)

# 最大化 3x+2y，约束 x+y<=4、x<=3、y<=3，变量非负，最优 (3,1) 值 11
BOUNDED = [([1, 1], 4), ([1, 0], 3), ([0, 1], 3)]
OBJECTIVE = [3, 2]


class TestParsing(unittest.TestCase):
    def test_to_fraction_accepts_int_fraction_float(self):
        self.assertEqual(to_fraction(3), Fraction(3))
        self.assertEqual(to_fraction(Fraction(1, 3)), Fraction(1, 3))
        self.assertEqual(to_fraction(0.5), Fraction(1, 2))

    def test_as_fraction_matches_to_fraction(self):
        self.assertEqual(as_fraction(Fraction(2, 5)), to_fraction(Fraction(2, 5)))

    def test_bool_rejected(self):
        with self.assertRaises(LinearProgramError):
            to_fraction(True)

    def test_unknown_type_rejected(self):
        with self.assertRaises(LinearProgramError):
            to_fraction("nope")

    def test_empty_coefficients_rejected(self):
        with self.assertRaises(LinearProgramError):
            naive_optimize([([], 1)], OBJECTIVE)

    def test_wrong_sense_rejected(self):
        with self.assertRaises(LinearProgramError):
            naive_optimize([([1, 1], 4, ">=")], OBJECTIVE)

    def test_wrong_tuple_length_rejected(self):
        with self.assertRaises(LinearProgramError):
            naive_optimize([([1, 1],)], OBJECTIVE)

    def test_constraints_not_sequence_rejected(self):
        with self.assertRaises(LinearProgramError):
            naive_optimize(5, OBJECTIVE)

    def test_objective_not_sequence_rejected(self):
        with self.assertRaises(LinearProgramError):
            naive_optimize(BOUNDED, 5)

    def test_error_is_exception(self):
        self.assertTrue(issubclass(LinearProgramError, Exception))

    def test_error_carries_position(self):
        try:
            naive_optimize([([1, 1], 4), ([1, 2], 3, ">=")], OBJECTIVE)
        except LinearProgramError as exc:
            self.assertEqual(exc.position, 1)
        else:
            self.fail("应当抛错")


class TestGeometry(unittest.TestCase):
    def test_intersection_of_two_lines(self):
        hit = refine_intersection(([1, 1], 4), ([1, 0], 3), 2)
        self.assertEqual(hit, [Fraction(3), Fraction(1)])

    def test_parallel_lines_have_no_intersection(self):
        self.assertIsNone(refine_intersection(([1, 1], 4), ([2, 2], 8), 2))

    def test_intersection_pads_missing_variables(self):
        hit = refine_intersection(([2, 0], 6), ([0, 3], 9), 2)
        self.assertEqual(hit, [Fraction(3), Fraction(3)])

    def test_all_constraint_pairs_is_quadratic(self):
        rows = [([1, 0], 1), ([0, 1], 1), ([1, 1], 1), ([1, -1], 1)]
        pairs = all_constraint_pairs(rows)
        self.assertEqual(len(pairs), 6)
        self.assertEqual(naive_vertex_count(rows), 6)

    def test_variables_seen_sorted(self):
        rows = [([0, 2, 0], 1), ([3, 0, 4], 2)]
        self.assertEqual(variables_seen(rows), [0, 1, 2])
        self.assertEqual(naive_covered_variables(rows), [0, 1, 2])


class TestFeasibility(unittest.TestCase):
    def test_point_inside_region(self):
        self.assertTrue(naive_is_feasible(BOUNDED, [Fraction(2), Fraction(1)]))

    def test_point_outside_region(self):
        self.assertFalse(naive_is_feasible(BOUNDED, [Fraction(4), Fraction(4)]))

    def test_negative_coordinate_rejected(self):
        self.assertFalse(naive_is_feasible(BOUNDED, [Fraction(-1), Fraction(0)]))

    def test_origin_feasible_without_constraints(self):
        self.assertTrue(naive_is_feasible([], [Fraction(0)]))

    def test_point_value_matches_objective(self):
        self.assertEqual(point_value(OBJECTIVE, [Fraction(2), Fraction(1)]), Fraction(8))
        self.assertEqual(naive_objective_value(OBJECTIVE, [Fraction(3), Fraction(1)]),
                         Fraction(11))


class TestNaiveSolve(unittest.TestCase):
    def test_bounded_problem_picks_best_vertex(self):
        status, value, point = naive_optimize(BOUNDED, OBJECTIVE)
        self.assertEqual(status, "optimal")
        self.assertEqual(value, Fraction(11))
        self.assertEqual(point, [Fraction(3), Fraction(1)])

    def test_infeasible_problem_reports_none(self):
        status, value, point = naive_optimize([([1, 1], -1)], OBJECTIVE)
        self.assertEqual(status, "infeasible")
        self.assertIsNone(value)
        self.assertIsNone(point)

    def test_tie_takes_first_larger_only(self):
        status, value, point = naive_optimize([([1, 0], 5)], [1])
        self.assertEqual(status, "optimal")
        self.assertEqual(value, Fraction(5))

    def test_single_variable_problem(self):
        status, value, point = naive_optimize([([1], 7)], [2])
        self.assertEqual(status, "optimal")
        self.assertEqual(value, Fraction(14))

    def test_handy_entries_agree_with_optimize(self):
        self.assertEqual(naive_maximize(BOUNDED, OBJECTIVE), Fraction(11))
        self.assertEqual(naive_status(BOUNDED, OBJECTIVE), "optimal")

    def test_eps_is_small_positive(self):
        self.assertTrue(EPS > 0)
        self.assertTrue(EPS < Fraction(1, 10 ** 6))

    def test_repeated_runs_are_identical(self):
        first = naive_optimize(BOUNDED, OBJECTIVE)
        for _ in range(3):
            self.assertEqual(naive_optimize(BOUNDED, OBJECTIVE), first)


if __name__ == "__main__":
    unittest.main()
