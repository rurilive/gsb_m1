"""参考最短路 dijkstra_path 的行为基线，供后续实现对拍。"""

import math
import unittest

from gridnav import (Grid, GridError, bfs_path, dijkstra_path, open_map,
                     path_cost, random_map)

SQRT2 = math.sqrt(2.0)


class DijkstraPathTest(unittest.TestCase):

    def test_matched_cost_flat(self):
        grid = Grid(5, 4)
        self.assertEqual(dijkstra_path(grid, (0, 0), (3, 0)),
                         [(0, 0), (1, 0), (2, 0), (3, 0)])

    def test_open_map_all_diagonals(self):
        grid = open_map(4, 4)
        self.assertEqual(dijkstra_path(grid, (0, 0), (3, 3)),
                         [(0, 0), (1, 1), (2, 2), (3, 3)])

    def test_cost_of_around_wall_path(self):
        grid = Grid(5, 5, [(2, y) for y in range(4)])
        path = dijkstra_path(grid, (0, 0), (4, 0))
        self.assertEqual(path_cost(grid, path), 4 * SQRT2 + 4.0)

    def test_cost_never_worse_than_bfs(self):
        grid = random_map(10, 8, density=0.25, seed=5,
                          protected=[(0, 0), (9, 7)])
        best = path_cost(grid, dijkstra_path(grid, (0, 0), (9, 7)))
        steps = path_cost(grid, bfs_path(grid, (0, 0), (9, 7)))
        self.assertLessEqual(best, steps + 1e-9)

    def test_returns_none_when_unreachable(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        self.assertIsNone(dijkstra_path(grid, (0, 0), (4, 4)))

    def test_endpoint_errors(self):
        grid = Grid(3, 3, [(0, 0)])
        with self.assertRaises(GridError):
            dijkstra_path(grid, (0, 0), (2, 2))
        with self.assertRaises(GridError):
            dijkstra_path(grid, (2, 2), (0, 4))

    def test_start_equals_goal(self):
        grid = Grid(3, 3)
        self.assertEqual(dijkstra_path(grid, (1, 2), (1, 2)), [(1, 2)])

    def test_equal_cost_choice_is_stable(self):
        grid = open_map(5, 5)
        first = dijkstra_path(grid, (0, 0), (2, 1))
        second = dijkstra_path(grid, (0, 0), (2, 1))
        self.assertEqual(first, second)
        self.assertEqual(path_cost(grid, first), SQRT2 + 1.0)

    def test_repeatable_on_random_map(self):
        grid = random_map(14, 10, density=0.28, seed=23,
                          protected=[(0, 0), (13, 9)])
        first = dijkstra_path(grid, (0, 0), (13, 9))
        self.assertIsNotNone(first)
        self.assertEqual(first, dijkstra_path(grid, (0, 0), (13, 9)))


if __name__ == "__main__":
    unittest.main()
