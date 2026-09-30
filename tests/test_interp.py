"""interp 现有行为的锁定测试：入口校验、范德蒙德铺行、朴素高斯消元、解系数求值、
多项式乘法、幂和枚举与规模对照。

只覆盖当前朴素实现已经给出的结果，后面新增的拉格朗日插值路、牛顿差分路、
分治乘法与秦九韶求值、幂和闭式与反求系数都另开文件。
"""

import unittest
from fractions import Fraction

from lagrange import (
    LagrangeError,
    naive_eval,
    naive_eval_cost,
    naive_fit_coefficients,
    naive_mul,
    naive_power_sum,
    naive_solve_cost,
    naive_value_at,
    normalize_points,
    solve_linear_system,
    to_fraction,
    vandermonde_rows,
)

# 过 (0,1)、(1,3)、(2,7) 的多项式是 x^2 + x + 1，低次在前
POINTS = [(0, 1), (1, 3), (2, 7)]


class TestParsing(unittest.TestCase):
    def test_to_fraction_accepts_int_fraction_float(self):
        self.assertEqual(to_fraction(3), Fraction(3))
        self.assertEqual(to_fraction(Fraction(1, 3)), Fraction(1, 3))
        self.assertEqual(to_fraction(0.5), Fraction(1, 2))

    def test_bool_rejected(self):
        with self.assertRaises(LagrangeError):
            to_fraction(True)

    def test_unknown_type_rejected(self):
        with self.assertRaises(LagrangeError):
            to_fraction("nope")


class TestNormalize(unittest.TestCase):
    def test_normalize_returns_fractions(self):
        self.assertEqual(normalize_points(POINTS), [(Fraction(0), Fraction(1)),
                                                    (Fraction(1), Fraction(3)),
                                                    (Fraction(2), Fraction(7))])

    def test_empty_rejected(self):
        with self.assertRaises(LagrangeError):
            normalize_points([])

    def test_none_rejected(self):
        with self.assertRaises(LagrangeError):
            normalize_points(None)

    def test_duplicate_x_rejected(self):
        with self.assertRaises(LagrangeError):
            normalize_points([(1, 2), (1, 5)])

    def test_bad_pair_rejected(self):
        with self.assertRaises(LagrangeError):
            normalize_points([(1, 2, 3)])


class TestVandermonde(unittest.TestCase):
    def test_rows_shape(self):
        rows = vandermonde_rows(normalize_points(POINTS), 2)
        self.assertEqual(rows, [
            [Fraction(1), Fraction(0), Fraction(0), Fraction(1)],
            [Fraction(1), Fraction(1), Fraction(1), Fraction(3)],
            [Fraction(1), Fraction(2), Fraction(4), Fraction(7)],
        ])

    def test_negative_degree_rejected(self):
        with self.assertRaises(LagrangeError):
            vandermonde_rows(normalize_points(POINTS), -1)


class TestSolveSystem(unittest.TestCase):
    def test_solves_small_system(self):
        rows = [[2, 1, 5], [1, -1, 1]]
        self.assertEqual(solve_linear_system(rows, 2), [Fraction(2), Fraction(1)])

    def test_mismatched_size_rejected(self):
        with self.assertRaises(LagrangeError):
            solve_linear_system([[1, 2]], 2)

    def test_zero_variables_rejected(self):
        with self.assertRaises(LagrangeError):
            solve_linear_system([], 0)


class TestFitAndEval(unittest.TestCase):
    def test_fit_quadratic(self):
        self.assertEqual(naive_fit_coefficients(POINTS),
                         [Fraction(1), Fraction(1), Fraction(1)])

    def test_eval_matches_known_polynomial(self):
        coeffs = naive_fit_coefficients(POINTS)
        self.assertEqual(naive_eval(coeffs, 3), Fraction(13))
        self.assertEqual(naive_eval(coeffs, -1), Fraction(1))
        self.assertEqual(naive_eval(coeffs, Fraction(1, 2)), Fraction(7, 4))

    def test_value_at_uses_fit_then_eval(self):
        self.assertEqual(naive_value_at(POINTS, 3), Fraction(13))

    def test_degree_mismatch_rejected(self):
        with self.assertRaises(LagrangeError):
            naive_fit_coefficients(POINTS, 5)


class TestMul(unittest.TestCase):
    def test_mul_linear_by_linear(self):
        self.assertEqual(naive_mul([1, 1], [1, -1]), [Fraction(1), Fraction(0), Fraction(-1)])

    def test_mul_empty_gives_empty(self):
        self.assertEqual(naive_mul([], [1, 2]), [])


class TestPowerSum(unittest.TestCase):
    def test_sum_of_squares(self):
        self.assertEqual(naive_power_sum(4, 2), Fraction(30))

    def test_sum_of_first_powers(self):
        self.assertEqual(naive_power_sum(5, 1), Fraction(15))

    def test_negative_limit_rejected(self):
        with self.assertRaises(LagrangeError):
            naive_power_sum(-1, 2)

    def test_bool_rejected(self):
        with self.assertRaises(LagrangeError):
            naive_power_sum(True, 2)


class TestCost(unittest.TestCase):
    def test_solve_cost_cubic(self):
        self.assertEqual(naive_solve_cost(3), 27)
        self.assertEqual(naive_solve_cost(0), 0)

    def test_eval_cost_triangular(self):
        self.assertEqual(naive_eval_cost(4), 10)
        self.assertEqual(naive_eval_cost(0), 0)


if __name__ == "__main__":
    unittest.main()
