"""BFS 寻路的行为基线：结果、并列选路与端点约定。"""

import unittest

from gridnav import Grid, GridError, bfs_path, open_map, random_map


class BfsPathTest(unittest.TestCase):

    def test_straight_line(self):
        grid = Grid(5, 4)
        self.assertEqual(bfs_path(grid, (0, 0), (3, 0)),
                         [(0, 0), (1, 0), (2, 0), (3, 0)])

    def test_start_equals_goal(self):
        grid = Grid(3, 3)
        self.assertEqual(bfs_path(grid, (2, 1), (2, 1)), [(2, 1)])

    def test_open_map_prefers_diagonals_first(self):
        grid = open_map(4, 4)
        self.assertEqual(bfs_path(grid, (0, 0), (3, 3)),
                         [(0, 0), (1, 1), (2, 2), (3, 3)])

    def test_around_wall_with_gap(self):
        grid = Grid(5, 5, [(2, y) for y in range(4)])
        self.assertEqual(
            bfs_path(grid, (0, 0), (4, 0)),
            [(0, 0), (1, 1), (1, 2), (1, 3), (2, 4),
             (3, 3), (3, 2), (3, 1), (4, 0)],
        )

    def test_random_map_is_reproducible(self):
        grid = random_map(9, 7, density=0.25, seed=7,
                          protected=[(0, 0), (8, 6)])
        self.assertEqual(
            bfs_path(grid, (0, 0), (8, 6)),
            [(0, 0), (1, 1), (2, 2), (3, 2), (4, 3),
             (5, 4), (6, 5), (7, 6), (8, 6)],
        )

    def test_unreachable_returns_none(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        self.assertIsNone(bfs_path(grid, (0, 0), (4, 4)))

    def test_blocked_endpoint_raises(self):
        grid = Grid(3, 3, [(0, 0)])
        with self.assertRaises(GridError):
            bfs_path(grid, (0, 0), (2, 2))
        with self.assertRaises(GridError):
            bfs_path(grid, (2, 2), (0, 0))

    def test_out_of_bounds_endpoint_raises(self):
        grid = Grid(3, 3)
        with self.assertRaises(GridError):
            bfs_path(grid, (-1, 0), (2, 2))
        with self.assertRaises(GridError):
            bfs_path(grid, (0, 0), (0, 3))

    def test_repeated_calls_agree(self):
        grid = random_map(12, 12, density=0.3, seed=5,
                          protected=[(0, 0), (11, 11)])
        first = bfs_path(grid, (0, 0), (11, 11))
        second = bfs_path(grid, (0, 0), (11, 11))
        self.assertIsNotNone(first)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
