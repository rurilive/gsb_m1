"""Grid 的尺寸、障碍、邻居与步长行为基线。"""

import unittest

from gridnav import DIRECTIONS, SQRT2, Grid, GridError


class GridBasicsTest(unittest.TestCase):

    def test_size_and_bounds(self):
        grid = Grid(3, 2)
        self.assertEqual((grid.width, grid.height), (3, 2))
        self.assertTrue(grid.in_bounds(0, 0))
        self.assertTrue(grid.in_bounds(2, 1))
        self.assertFalse(grid.in_bounds(3, 1))
        self.assertFalse(grid.in_bounds(1, 2))
        self.assertFalse(grid.in_bounds(-1, 0))

    def test_bad_size_rejected(self):
        for width, height in ((0, 3), (3, 0), (-1, 3), (2.5, 3), ("3", 3)):
            with self.assertRaises(GridError):
                Grid(width, height)

    def test_blocked_argument(self):
        grid = Grid(3, 3, [(1, 1), (0, 2)])
        self.assertTrue(grid.is_blocked(1, 1))
        self.assertEqual(grid.blocked_cells(), ((0, 2), (1, 1)))
        self.assertFalse(grid.is_blocked(2, 2))

    def test_blocked_argument_out_of_bounds(self):
        with self.assertRaises(GridError):
            Grid(3, 3, [(3, 0)])

    def test_out_of_bounds_queries_raise(self):
        grid = Grid(3, 3)
        with self.assertRaises(GridError):
            grid.is_blocked(3, 0)
        with self.assertRaises(GridError):
            grid.neighbors(0, -1)
        with self.assertRaises(GridError):
            grid.set_blocked(0, 9)

    def test_passable_is_total(self):
        grid = Grid(3, 3, [(1, 1)])
        self.assertTrue(grid.passable(0, 0))
        self.assertFalse(grid.passable(1, 1))
        self.assertFalse(grid.passable(5, 5))

    def test_set_blocked_returns_previous_state(self):
        grid = Grid(2, 2)
        self.assertFalse(grid.set_blocked(1, 0))
        self.assertTrue(grid.set_blocked(1, 0))
        self.assertTrue(grid.set_blocked(1, 0, False))
        self.assertFalse(grid.is_blocked(1, 0))
        self.assertFalse(grid.set_blocked(1, 0, False))

    def test_blocked_cells_sorted(self):
        grid = Grid(4, 4, [(3, 1), (0, 0), (1, 3)])
        self.assertEqual(grid.blocked_cells(), ((0, 0), (1, 3), (3, 1)))

    def test_copy_is_independent(self):
        grid = Grid(3, 3, [(1, 1)])
        clone = grid.copy()
        clone.set_blocked(0, 0)
        self.assertTrue(clone.is_blocked(0, 0))
        self.assertFalse(grid.is_blocked(0, 0))
        self.assertTrue(grid.is_blocked(1, 1))

    def test_require_cell(self):
        grid = Grid(3, 3, [(1, 1)])
        self.assertEqual(grid.require_cell((0, 2), "start"), (0, 2))
        with self.assertRaises(GridError):
            grid.require_cell((1, 1), "goal")
        with self.assertRaises(GridError):
            grid.require_cell((5, 5), "start")
        with self.assertRaises(GridError):
            grid.require_cell(7, "start")


class NeighborTest(unittest.TestCase):

    def test_interior_order_and_costs(self):
        grid = Grid(3, 3)
        expected = tuple(
            (1 + dx, 1 + dy, SQRT2 if dx != 0 and dy != 0 else 1.0)
            for dx, dy in DIRECTIONS
        )
        self.assertEqual(grid.neighbors(1, 1), expected)

    def test_corner_cell_has_three_neighbors(self):
        grid = Grid(3, 3)
        self.assertEqual(
            grid.neighbors(0, 0),
            ((1, 0, 1.0), (1, 1, SQRT2), (0, 1, 1.0)),
        )

    def test_blocked_neighbor_skipped(self):
        grid = Grid(3, 3)
        grid.set_blocked(2, 1)
        cells = [cell for cell in grid.neighbors(1, 1)]
        self.assertNotIn((2, 1, 1.0), cells)

    def test_both_orthogonals_blocked_forbids_diagonal(self):
        grid = Grid(3, 3)
        grid.set_blocked(2, 1)
        grid.set_blocked(1, 2)
        cells = [(nx, ny) for nx, ny, _c in grid.neighbors(1, 1)]
        self.assertNotIn((2, 2), cells)
        self.assertIn((0, 0), cells)

    def test_single_blocked_orthogonal_still_slides(self):
        grid = Grid(3, 3)
        grid.set_blocked(2, 1)
        cells = [(nx, ny) for nx, ny, _c in grid.neighbors(1, 1)]
        self.assertIn((2, 2), cells)

    def test_step_cost(self):
        grid = Grid(3, 3)
        self.assertEqual(grid.step_cost((0, 0), (1, 0)), 1.0)
        self.assertEqual(grid.step_cost((0, 0), (0, 1)), 1.0)
        self.assertEqual(grid.step_cost((0, 0), (1, 1)), SQRT2)
        self.assertEqual(grid.step_cost((1, 1), (0, 0)), SQRT2)
        with self.assertRaises(GridError):
            grid.step_cost((0, 0), (2, 0))
        with self.assertRaises(GridError):
            grid.step_cost((0, 0), (0, 0))


if __name__ == "__main__":
    unittest.main()
