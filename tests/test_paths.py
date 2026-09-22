"""路径校验与代价计算的行为基线。"""

import math
import unittest

from gridnav import Grid, PathError, path_cost, validate_path

SQRT2 = math.sqrt(2.0)


class PathCostTest(unittest.TestCase):

    def test_orthogonal_steps(self):
        grid = Grid(4, 4)
        self.assertEqual(path_cost(grid, [(0, 0), (1, 0), (2, 0), (3, 0)]), 3.0)

    def test_diagonal_steps(self):
        grid = Grid(4, 4)
        self.assertEqual(path_cost(grid, [(0, 0), (1, 1), (2, 2), (3, 3)]),
                         3 * SQRT2)

    def test_mixed_steps(self):
        grid = Grid(4, 4)
        cost = path_cost(grid, [(0, 0), (1, 1), (2, 1), (3, 1)])
        self.assertEqual(cost, SQRT2 + 1.0 + 1.0)

    def test_single_cell_costs_zero(self):
        grid = Grid(3, 3)
        self.assertEqual(path_cost(grid, [(1, 1)]), 0.0)

    def test_path_may_use_lists(self):
        grid = Grid(3, 3)
        self.assertEqual(path_cost(grid, [[0, 0], [1, 0]]), 1.0)


class PathValidationTest(unittest.TestCase):

    def test_accepts_legal_path(self):
        grid = Grid(3, 3, [(2, 0)])
        self.assertIsNone(validate_path(grid, [(0, 0), (1, 0), (1, 1)]))

    def test_rejects_empty(self):
        grid = Grid(3, 3)
        with self.assertRaises(PathError):
            validate_path(grid, [])

    def test_rejects_jump(self):
        grid = Grid(4, 4)
        with self.assertRaises(PathError):
            validate_path(grid, [(0, 0), (2, 0)])

    def test_rejects_repeat(self):
        grid = Grid(4, 4)
        with self.assertRaises(PathError):
            validate_path(grid, [(0, 0), (0, 0)])

    def test_rejects_cell_out_of_bounds(self):
        grid = Grid(3, 3)
        with self.assertRaises(PathError):
            validate_path(grid, [(0, 0), (0, 3)])

    def test_rejects_blocked_cell(self):
        grid = Grid(3, 3, [(1, 0)])
        with self.assertRaises(PathError):
            validate_path(grid, [(0, 0), (1, 0), (2, 0)])

    def test_rejects_corner_cut(self):
        grid = Grid(3, 3)
        grid.set_blocked(1, 0)
        grid.set_blocked(0, 1)
        with self.assertRaises(PathError):
            validate_path(grid, [(0, 0), (1, 1)])

    def test_allows_sliding_past_one_wall(self):
        grid = Grid(3, 3)
        grid.set_blocked(1, 0)
        self.assertIsNone(validate_path(grid, [(0, 0), (1, 1)]))


if __name__ == "__main__":
    unittest.main()
