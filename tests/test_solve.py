"""solve 现有行为的锁定测试：形状校验、朴素消元、有无解判定、求秩、求行列式、
自由变量与文本解析。

只覆盖当前朴素实现已经给出的结果，后面新增的选主元、约当回代、模素数域印证
与规模对照另开文件。
"""

import unittest
from fractions import Fraction

from linearsolve import (
    LinearSolveError,
    build_augmented,
    naive_determinant,
    naive_free_symbols,
    naive_is_consistent,
    naive_rank,
    naive_solve,
    naive_solve_matrix,
    parse_matrix_text,
)

# 三元一次方程组，唯一解 x=2, y=3, z=-1
UNIQUE3 = [[2, 1, -1, 8], [-3, -1, 2, -11], [-2, 1, 2, -3]]
# 二元一次方程组，唯一解 x=2, y=1
UNIQUE2 = [[2, 1, 5], [1, -1, 1]]
SINGULAR = [[1, 2, 3], [2, 4, 6]]          # 两个方程成比例，无穷多解
NONE = [[1, 2, 3], [2, 4, 7]]              # 系数成比例而常数项不成比例，无解


class TestShape(unittest.TestCase):
    def test_accepts_ragged_free_rectangle(self):
        self.assertEqual(naive_rank(UNIQUE3), 3)
        self.assertEqual(naive_rank([[1, 2, 3, 4, 5]]), 1)

    def test_empty_matrix_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_rank([])

    def test_ragged_matrix_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_rank([[1, 2, 3], [4, 5]])

    def test_width_too_small_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_rank([[1], [2]])

    def test_bool_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_rank([[1, True, 3]])

    def test_non_number_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_rank([[1, 2.5, 3]])

    def test_error_is_exception(self):
        self.assertTrue(issubclass(LinearSolveError, Exception))


class TestSolve(unittest.TestCase):
    def test_unique_three(self):
        self.assertEqual(naive_solve(UNIQUE3), [2, 3, -1])

    def test_unique_two(self):
        self.assertEqual(naive_solve(UNIQUE2), [2, 1])

    def test_unique_status_and_value(self):
        status, solution = naive_solve_matrix(UNIQUE3)
        self.assertEqual(status, "唯一解")
        self.assertEqual(solution, [2, 3, -1])

    def test_fraction_solution(self):
        matrix = [[2, 0, 1], [0, 3, 1]]
        self.assertEqual(naive_solve(matrix), [Fraction(1, 2), Fraction(1, 3)])

    def test_infinite(self):
        status, solution = naive_solve_matrix(SINGULAR)
        self.assertEqual(status, "无穷多解")
        self.assertIsNone(solution)

    def test_no_solution(self):
        status, solution = naive_solve_matrix(NONE)
        self.assertEqual(status, "无解")
        self.assertIsNone(solution)

    def test_naive_solve_returns_none_for_singular(self):
        self.assertIsNone(naive_solve(SINGULAR))
        self.assertIsNone(naive_solve(NONE))


class TestConsistency(unittest.TestCase):
    def test_consistent(self):
        self.assertTrue(naive_is_consistent(UNIQUE3))
        self.assertTrue(naive_is_consistent(SINGULAR))

    def test_inconsistent(self):
        self.assertFalse(naive_is_consistent(NONE))


class TestRank(unittest.TestCase):
    def test_full_rank_square(self):
        self.assertEqual(naive_rank(UNIQUE3), 3)

    def test_rank_deficient(self):
        self.assertEqual(naive_rank(SINGULAR), 1)

    def test_rank_wide(self):
        self.assertEqual(naive_rank([[1, 2, 0, 3], [0, 0, 0, 0]]), 1)


class TestDet(unittest.TestCase):
    def test_two_by_two(self):
        self.assertEqual(naive_determinant([[1, 2, 0], [3, 4, 0]]), Fraction(-2))

    def test_identity_three(self):
        self.assertEqual(naive_determinant([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]),
                         Fraction(1))

    def test_three_by_three(self):
        self.assertEqual(naive_determinant([[2, 1, 1, 0], [1, 3, 2, 0], [1, 0, 0, 0]]),
                         Fraction(-1))

    def test_singular_is_zero(self):
        self.assertEqual(naive_determinant([[1, 2, 0], [2, 4, 0]]), Fraction(0))

    def test_empty_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_determinant([])

    def test_non_square_rejected(self):
        with self.assertRaises(LinearSolveError):
            naive_determinant([[1, 2, 3, 4], [5, 6, 7, 8]])


class TestFreeSymbols(unittest.TestCase):
    def test_zero_column_is_free(self):
        self.assertEqual(naive_free_symbols([[1, 0, 2], [0, 0, 0]]), [1])

    def test_no_free_when_all_columns_used(self):
        self.assertEqual(naive_free_symbols(UNIQUE2), [])


class TestTextAndBuild(unittest.TestCase):
    def test_parse_simple(self):
        grid = parse_matrix_text("1 2 | 3\n4 5 | 6")
        self.assertEqual(grid, [[Fraction(1), Fraction(2), Fraction(3)],
                                [Fraction(4), Fraction(5), Fraction(6)]])

    def test_parse_fraction_token(self):
        grid = parse_matrix_text("1/2 1 | 3")
        self.assertEqual(grid, [[Fraction(1, 2), Fraction(1), Fraction(3)]])

    def test_parse_missing_separator_rejected(self):
        with self.assertRaises(LinearSolveError):
            parse_matrix_text("1 2 3")

    def test_parse_two_separators_rejected(self):
        with self.assertRaises(LinearSolveError):
            parse_matrix_text("1 2 | 3 | 4")

    def test_parse_bad_number_rejected(self):
        with self.assertRaises(LinearSolveError):
            parse_matrix_text("1 x | 3")

    def test_parse_empty_rejected(self):
        with self.assertRaises(LinearSolveError):
            parse_matrix_text("   \n  ")

    def test_build_augmented(self):
        self.assertEqual(build_augmented([[1, 2], [3, 4]], [5, 6]),
                         [[1, 2, 5], [3, 4, 6]])

    def test_build_length_mismatch_rejected(self):
        with self.assertRaises(LinearSolveError):
            build_augmented([[1, 2], [3, 4]], [5])


class TestScaleCounts(unittest.TestCase):
    def test_expansion_ops_factorial(self):
        from linearsolve.solve import expansion_ops
        self.assertEqual(expansion_ops(0), 1)
        self.assertEqual(expansion_ops(3), 6)
        self.assertEqual(expansion_ops(5), 120)

    def test_elimination_ops_grows_slower(self):
        from linearsolve.solve import elimination_ops
        self.assertEqual(elimination_ops(0, 3), 0)
        self.assertEqual(elimination_ops(3, 3), 18)
        self.assertLess(elimination_ops(5, 5), 125)


class TestDeterminism(unittest.TestCase):
    def test_repeat_solve_stable(self):
        self.assertEqual(naive_solve(UNIQUE3), naive_solve(UNIQUE3))

    def test_repeat_rank_stable(self):
        self.assertEqual(naive_rank(SINGULAR), naive_rank(SINGULAR))

    def test_repeat_det_stable(self):
        self.assertEqual(naive_determinant([[1, 2, 0], [3, 4, 0]]),
                         naive_determinant([[1, 2, 0], [3, 4, 0]]))


if __name__ == "__main__":
    unittest.main()
