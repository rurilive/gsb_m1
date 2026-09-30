"""基线测试：锁住改造前 maxrect.rect.MaxRect 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - brute_max_rect 枚举全部上下左右四元组，逐格验证全一，求最大面积与一个位置；
  - brute_max_square 枚举全部正方形候选，逐格验证全一，求最大边长与面积；
  - brute_max_weight 枚举全部候选矩形，逐格累计权值，求最大权值和与一个位置；
  - simple_heights 在每一格向上数连续一的长度，返回高度整表；
  - independent_suspend 是直接用悬线法思想实现的一条独立慢速做法，与主路径对账。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maxrect.rect import (  # noqa: E402
    MaxRect,
    Erro,
    ShapeErro,
    ValueErro,
    MONOTONIC,
    SUSPEND,
    NAIVE,
)

EMPTY = []
EMPTY_ROW = [[]]
SINGLE_ZERO = [[0]]
SINGLE_ONE = [[1]]
ALL_ZERO = [[0, 0], [0, 0]]
ALL_ONE_2X3 = [[1, 1, 1], [1, 1, 1]]
SINGLE_ROW = [[1, 1, 0, 1]]
SINGLE_COL = [[1], [1], [0], [1]]
ZERO_SEP = [[1, 1, 0, 0], [1, 0, 0, 1], [1, 1, 1, 1]]
TIED = [[1, 1, 0], [1, 1, 1], [1, 1, 1]]
BORDER = [[1, 1, 1], [1, 1, 1]]


def valid_rect(grid, rect):
    top, left, bottom, right = rect
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            if grid[r][c] != 1:
                return False
    return True


class TestErrors(unittest.TestCase):
    def test_hierarchy(self):
        self.assertTrue(issubclass(ShapeErro, Erro))
        self.assertTrue(issubclass(ValueErro, Erro))
        self.assertTrue(issubclass(Erro, Exception))

    def test_scale_labels(self):
        self.assertEqual(len({MONOTONIC, SUSPEND, NAIVE}), 3)

    def test_not_a_matrix(self):
        with self.assertRaises(ShapeErro):
            MaxRect(5)

    def test_row_not_sequence(self):
        with self.assertRaises(ShapeErro):
            MaxRect([[1], 2])

    def test_ragged(self):
        with self.assertRaises(ShapeErro):
            MaxRect([[1, 0], [1]])

    def test_value_out_of_range(self):
        with self.assertRaises(ShapeErro):
            MaxRect([[0, 2]])

    def test_negative_value(self):
        with self.assertRaises(ShapeErro):
            MaxRect([[0, -1]])

    def test_bool_is_not_zero_one(self):
        with self.assertRaises(ShapeErro):
            MaxRect([[True]])

    def test_weight_shape_mismatch(self):
        with self.assertRaises(ValueErro):
            MaxRect([[1, 1]]).brute_max_weight([[1, 1], [1, 1]])

    def test_weight_not_number(self):
        with self.assertRaises(ValueErro):
            MaxRect([[1, 1]]).brute_max_weight([[1, "x"]])

    def test_weight_bool_rejected(self):
        with self.assertRaises(ValueErro):
            MaxRect([[1]]).brute_max_weight([[True]])

    def test_weight_not_matrix(self):
        with self.assertRaises(ShapeErro):
            MaxRect([[1]]).brute_max_weight(5)


class TestDimensions(unittest.TestCase):
    def test_empty(self):
        m = MaxRect(EMPTY)
        self.assertEqual((m.rows, m.cols), (0, 0))

    def test_one_empty_row(self):
        m = MaxRect(EMPTY_ROW)
        self.assertEqual((m.rows, m.cols), (1, 0))

    def test_regular(self):
        self.assertEqual((MaxRect(ALL_ONE_2X3).rows, MaxRect(ALL_ONE_2X3).cols), (2, 3))


class TestMaxRect(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(MaxRect(EMPTY).brute_max_rect(), (0, None))

    def test_single_zero(self):
        self.assertEqual(MaxRect(SINGLE_ZERO).brute_max_rect(), (0, None))

    def test_single_one(self):
        self.assertEqual(MaxRect(SINGLE_ONE).brute_max_rect(), (1, (0, 0, 0, 0)))

    def test_all_zero(self):
        self.assertEqual(MaxRect(ALL_ZERO).brute_max_rect(), (0, None))

    def test_all_one(self):
        self.assertEqual(MaxRect(ALL_ONE_2X3).brute_max_rect(), (6, (0, 0, 1, 2)))

    def test_single_row(self):
        self.assertEqual(MaxRect(SINGLE_ROW).brute_max_rect(), (2, (0, 0, 0, 1)))

    def test_single_col(self):
        self.assertEqual(MaxRect(SINGLE_COL).brute_max_rect(), (2, (0, 0, 1, 0)))

    def test_zero_sep(self):
        self.assertEqual(MaxRect(ZERO_SEP).brute_max_rect(), (4, (2, 0, 2, 3)))

    def test_tie_lex_smallest(self):
        self.assertEqual(MaxRect(TIED).brute_max_rect(), (6, (0, 0, 2, 1)))

    def test_border_touching(self):
        self.assertEqual(MaxRect(BORDER).brute_max_rect(), (6, (0, 0, 1, 2)))

    def test_visits(self):
        m = MaxRect(BORDER)
        m.brute_max_rect()
        self.assertEqual(m.rect_visits, 18)

    def test_cell_checks(self):
        m = MaxRect(BORDER)
        m.brute_max_rect()
        self.assertEqual(m.cell_checks, 40)

    def test_properties_reflect_last_run(self):
        m = MaxRect(ALL_ONE_2X3)
        m.brute_max_rect()
        self.assertEqual(m.best_area, 6)
        self.assertEqual(m.best_rect, (0, 0, 1, 2))

    def test_visits_formula(self):
        m = MaxRect(TIED)
        m.brute_max_rect()
        self.assertEqual(m.rect_visits, 36)


class TestMaxSquare(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(MaxRect(EMPTY).brute_max_square(), (0, 0))

    def test_single_zero(self):
        self.assertEqual(MaxRect(SINGLE_ZERO).brute_max_square(), (0, 0))

    def test_single_one(self):
        self.assertEqual(MaxRect(SINGLE_ONE).brute_max_square(), (1, 1))

    def test_all_one(self):
        self.assertEqual(MaxRect(ALL_ONE_2X3).brute_max_square(), (4, 2))

    def test_single_row(self):
        self.assertEqual(MaxRect(SINGLE_ROW).brute_max_square(), (1, 1))

    def test_zero_sep(self):
        self.assertEqual(MaxRect(ZERO_SEP).brute_max_square(), (1, 1))


class TestMaxWeight(unittest.TestCase):
    def test_positive_block(self):
        self.assertEqual(MaxRect(ALL_ONE_2X3).brute_max_weight([[1, 1, 1], [1, 1, 1]]),
                         (6, (0, 0, 1, 2)))

    def test_all_negative_picks_lex_smallest(self):
        self.assertEqual(MaxRect(SINGLE_ROW).brute_max_weight([[-1, -3, -2, -4]]),
                         (-1, (0, 0, 0, 0)))

    def test_mixed(self):
        grid = [[1, 1, 1], [1, 1, 1]]
        weight = [[2, -5, 2], [2, 2, 2]]
        self.assertEqual(MaxRect(grid).brute_max_weight(weight), (6, (1, 0, 1, 2)))

    def test_empty_returns_zero(self):
        self.assertEqual(MaxRect(EMPTY).brute_max_weight([]), (0, None))


class TestHeights(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(MaxRect(EMPTY).simple_heights(), [])

    def test_one_empty_row(self):
        self.assertEqual(MaxRect(EMPTY_ROW).simple_heights(), [[]])

    def test_single_zero(self):
        self.assertEqual(MaxRect(SINGLE_ZERO).simple_heights(), [[0]])

    def test_single_one(self):
        self.assertEqual(MaxRect(SINGLE_ONE).simple_heights(), [[1]])

    def test_all_one(self):
        self.assertEqual(MaxRect(ALL_ONE_2X3).simple_heights(), [[1, 1, 1], [2, 2, 2]])

    def test_zero_sep(self):
        self.assertEqual(MaxRect(ZERO_SEP).simple_heights(),
                         [[1, 1, 0, 0], [2, 0, 0, 1], [3, 1, 1, 2]])

    def test_single_row(self):
        self.assertEqual(MaxRect(SINGLE_ROW).simple_heights(), [[1, 1, 0, 1]])


class TestIndependentSuspend(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(MaxRect(EMPTY).independent_suspend(), (0, None))

    def test_single_one(self):
        self.assertEqual(MaxRect(SINGLE_ONE).independent_suspend(), (1, (0, 0, 0, 0)))

    def test_area_matches_brute(self):
        for grid in (ALL_ONE_2X3, SINGLE_ROW, SINGLE_COL, ZERO_SEP, TIED, BORDER, ALL_ZERO):
            with self.subTest(grid=grid):
                m = MaxRect(grid)
                area, _ = m.brute_max_rect()
                self.assertEqual(m.independent_suspend()[0], area)

    def test_rect_is_valid(self):
        for grid in (ALL_ONE_2X3, ZERO_SEP, TIED, BORDER):
            with self.subTest(grid=grid):
                area, rect = MaxRect(grid).independent_suspend()
                self.assertTrue(valid_rect(grid, rect))
                top, left, bottom, right = rect
                self.assertEqual((bottom - top + 1) * (right - left + 1), area)

    def test_border_area(self):
        self.assertEqual(MaxRect(BORDER).independent_suspend()[0], 6)


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_instance(self):
        m = MaxRect(ZERO_SEP)
        first = m.brute_max_rect()
        second = m.brute_max_rect()
        self.assertEqual(first, second)
        self.assertEqual(m.rect_visits, 60)

    def test_fresh_instances_agree(self):
        self.assertEqual(MaxRect(TIED).brute_max_rect(), MaxRect(TIED).brute_max_rect())

    def test_state_not_leaked_into_counts(self):
        m = MaxRect(ALL_ONE_2X3)
        m.brute_max_rect()
        visits = m.rect_visits
        m.simple_heights()
        m.brute_max_rect()
        self.assertEqual(m.rect_visits, visits)


if __name__ == "__main__":
    unittest.main()
