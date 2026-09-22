"""AStarPlanner 的行为基线：最优性、增量修复、可复现性与性能。"""

import ast
import inspect
import math
import os
import random
import subprocess
import sys
import time
import unittest

from gridnav import (Grid, GridError, dijkstra_path, open_map, path_cost,
                     random_map, validate_path)
from gridnav.astar import AStarPlanner

SQRT2 = math.sqrt(2.0)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HeuristicTest(unittest.TestCase):
    """对角线启发式的取值与舍入规则：锁死，不许再漂。"""

    def test_goal_is_zero(self):
        self.assertEqual(AStarPlanner.heuristic((2, 3), (2, 3)), 0.0)

    def test_straight_line_shrunk_below_true_cost(self):
        h = AStarPlanner.heuristic((0, 0), (3, 0))
        self.assertLess(h, 3.0)
        self.assertGreater(h, 3.0 - 1e-6)

    def test_pure_diagonal_shrunk_below_true_cost(self):
        h = AStarPlanner.heuristic((0, 0), (2, 2))
        self.assertLess(h, 2 * SQRT2)
        self.assertGreater(h, 2 * SQRT2 - 1e-6)

    def test_mixed_steps_shrunk_below_true_cost(self):
        h = AStarPlanner.heuristic((0, 0), (2, 1))
        self.assertLess(h, SQRT2 + 1.0)
        self.assertGreater(h, SQRT2 + 1.0 - 1e-6)

    def test_symmetric(self):
        self.assertEqual(AStarPlanner.heuristic((1, 2), (5, 7)),
                         AStarPlanner.heuristic((5, 7), (1, 2)))

    def test_never_exceeds_dijkstra_cost_on_random_maps(self):
        for seed in range(6):
            grid = random_map(20, 15, density=0.25, seed=seed,
                              protected=[(0, 0), (19, 14)])
            ref = dijkstra_path(grid, (0, 0), (19, 14))
            if ref is None:
                continue
            self.assertLessEqual(AStarPlanner.heuristic((0, 0), (19, 14)),
                                 path_cost(grid, ref))


class PlanOptimalityTest(unittest.TestCase):

    def test_open_map_diagonal(self):
        grid = open_map(4, 4)
        planner = AStarPlanner(grid)
        path = planner.plan((0, 0), (3, 3))
        self.assertEqual(path_cost(grid, path), 3 * SQRT2)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (3, 3))

    def test_start_equals_goal(self):
        planner = AStarPlanner(Grid(3, 3))
        self.assertEqual(planner.plan((1, 2), (1, 2)), [(1, 2)])
        self.assertEqual(planner.replan((1, 2), (1, 2)), [(1, 2)])

    def test_random_maps_cost_strictly_equals_dijkstra(self):
        cases = [
            (30, 20, 0.20), (25, 25, 0.30), (40, 15, 0.25), (18, 18, 0.35),
        ]
        for width, height, density in cases:
            for seed in range(5):
                grid = random_map(width, height, density=density, seed=seed,
                                  protected=[(0, 0), (width - 1, height - 1)])
                start, goal = (0, 0), (width - 1, height - 1)
                ref = dijkstra_path(grid, start, goal)
                mine = AStarPlanner(grid).plan(start, goal)
                if ref is None:
                    self.assertIsNone(mine)
                    continue
                self.assertIsNotNone(mine)
                validate_path(grid, mine)
                self.assertEqual(mine[0], start)
                self.assertEqual(mine[-1], goal)
                self.assertEqual(path_cost(grid, mine),
                                 path_cost(grid, ref))

    def test_unreachable_returns_none(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        self.assertIsNone(AStarPlanner(grid).plan((0, 0), (4, 4)))

    def test_surrounded_start_returns_none(self):
        grid = Grid(4, 4, [(1, 0), (0, 1), (1, 1)])
        self.assertIsNone(AStarPlanner(grid).plan((0, 0), (3, 3)))

    def test_surrounded_goal_returns_none(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        self.assertIsNone(AStarPlanner(grid).plan((0, 0), (4, 4)))

    def test_blocked_endpoint_raises(self):
        grid = Grid(3, 3, [(0, 0)])
        planner = AStarPlanner(grid)
        with self.assertRaises(GridError):
            planner.plan((0, 0), (2, 2))
        with self.assertRaises(GridError):
            planner.plan((2, 2), (0, 0))
        with self.assertRaises(GridError):
            planner.replan((0, 0), (2, 2))

    def test_out_of_bounds_endpoint_raises(self):
        planner = AStarPlanner(Grid(3, 3))
        with self.assertRaises(GridError):
            planner.plan((-1, 0), (2, 2))
        with self.assertRaises(GridError):
            planner.replan((0, 0), (0, 3))

    def test_tie_break_is_deterministic(self):
        grid = random_map(24, 18, density=0.28, seed=33,
                          protected=[(0, 0), (23, 17)])
        first = AStarPlanner(grid).plan((0, 0), (23, 17))
        self.assertIsNotNone(first)
        again = AStarPlanner(grid).plan((0, 0), (23, 17))
        self.assertEqual(first, again)
        planner = AStarPlanner(grid)
        self.assertEqual(planner.plan((0, 0), (23, 17)),
                         planner.plan((0, 0), (23, 17)))

    def test_open_list_is_a_heap(self):
        import gridnav.astar as astar_module
        self.assertIn("heapq", inspect.getsource(astar_module))


class ReplanTest(unittest.TestCase):

    def _planned(self, seed=13, size=60, density=0.2):
        grid = random_map(size, size, density=density, seed=seed,
                          protected=[(0, 0), (size - 1, size - 1)])
        planner = AStarPlanner(grid)
        goal = (size - 1, size - 1)
        path = planner.plan((0, 0), goal)
        self.assertIsNotNone(path)
        return grid, planner, (0, 0), goal, path

    def test_replan_without_changes_does_nothing(self):
        grid, planner, start, goal, path = self._planned()
        before = planner.stats()["expansions"]
        self.assertEqual(planner.replan(start, goal), path)
        stats = planner.stats()
        self.assertEqual(stats["last_expansions"], 0)
        self.assertEqual(stats["expansions"], before)

    def test_block_off_path_cell_not_reopened(self):
        ring = [(15 + dx, 15 + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx, dy) != (0, 0)]
        grid = Grid(21, 21, ring)
        planner = AStarPlanner(grid)
        path = planner.plan((0, 0), (20, 20))
        self.assertIsNotNone(path)
        self.assertNotIn((15, 15), path)
        before = planner.stats()["expansions"]
        grid.set_blocked(15, 15)
        self.assertEqual(planner.replan((0, 0), (20, 20)), path)
        stats = planner.stats()
        self.assertEqual(stats["last_expansions"], 0)
        self.assertEqual(stats["expansions"], before)

    def test_block_on_path_repairs_incrementally(self):
        grid, planner, start, goal, path = self._planned()
        full = planner.stats()["expansions"]
        hit = path[len(path) // 2]
        grid.set_blocked(hit[0], hit[1])
        ref = dijkstra_path(grid, start, goal)
        self.assertIsNotNone(ref)
        repaired = planner.replan(start, goal)
        self.assertIsNotNone(repaired)
        validate_path(grid, repaired)
        self.assertNotIn(hit, repaired)
        self.assertEqual(path_cost(grid, repaired), path_cost(grid, ref))
        stats = planner.stats()
        delta = stats["last_expansions"]
        self.assertGreater(delta, 0)
        self.assertLess(delta, full)
        self.assertEqual(stats["expansions"], full + delta)
        fresh = AStarPlanner(grid)
        fresh_path = fresh.plan(start, goal)
        self.assertEqual(path_cost(grid, fresh_path), path_cost(grid, repaired))
        self.assertLess(delta, fresh.stats()["expansions"])

    def test_unblock_restores_optimal(self):
        grid, planner, start, goal, path = self._planned()
        original_cost = path_cost(grid, path)
        hit = path[len(path) // 2]
        grid.set_blocked(hit[0], hit[1])
        planner.replan(start, goal)
        grid.set_blocked(hit[0], hit[1], False)
        restored = planner.replan(start, goal)
        self.assertIsNotNone(restored)
        validate_path(grid, restored)
        self.assertEqual(path_cost(grid, restored), original_cost)
        self.assertEqual(path_cost(grid, restored),
                         path_cost(grid, dijkstra_path(grid, start, goal)))

    def test_replan_to_unreachable_and_back(self):
        grid = open_map(10, 10)
        planner = AStarPlanner(grid)
        start, goal = (0, 0), (9, 9)
        self.assertIsNotNone(planner.plan(start, goal))
        for y in range(10):
            grid.set_blocked(5, y)
        self.assertIsNone(planner.replan(start, goal))
        grid.set_blocked(5, 5, False)
        path = planner.replan(start, goal)
        self.assertIsNotNone(path)
        validate_path(grid, path)
        self.assertEqual(path_cost(grid, path),
                         path_cost(grid, dijkstra_path(grid, start, goal)))

    def test_replan_with_new_endpoints_falls_back_to_full_search(self):
        grid = random_map(20, 20, density=0.25, seed=8,
                          protected=[(0, 0), (19, 19), (5, 2)])
        planner = AStarPlanner(grid)
        planner.plan((0, 0), (19, 19))
        path = planner.replan((0, 0), (5, 2))
        self.assertEqual(path_cost(grid, path),
                         path_cost(grid, dijkstra_path(grid, (0, 0), (5, 2))))

    def test_replan_blocked_endpoint_raises(self):
        grid = open_map(6, 6)
        planner = AStarPlanner(grid)
        planner.plan((0, 0), (5, 5))
        grid.set_blocked(5, 5)
        with self.assertRaises(GridError):
            planner.replan((0, 0), (5, 5))

    def test_stats_keys_and_counters(self):
        grid = open_map(8, 8)
        planner = AStarPlanner(grid)
        planner.plan((0, 0), (7, 7))
        planner.replan((0, 0), (7, 7))
        stats = planner.stats()
        self.assertEqual(stats["plans"], 1)
        self.assertEqual(stats["replans"], 1)
        self.assertGreater(stats["expansions"], 0)
        self.assertIn("last_expansions", stats)


class ReproducibilityTest(unittest.TestCase):

    def test_cross_process_identical_path(self):
        code = (
            "from gridnav import random_map\n"
            "from gridnav.astar import AStarPlanner\n"
            "g = random_map(40, 30, density=0.25, seed=11,\n"
            "             protected=[(0, 0), (39, 29)])\n"
            "print(repr(AStarPlanner(g).plan((0, 0), (39, 29))))\n"
        )
        out = subprocess.check_output([sys.executable, "-c", code],
                                      cwd=REPO_ROOT)
        other = ast.literal_eval(out.decode().strip())
        grid = random_map(40, 30, density=0.25, seed=11,
                          protected=[(0, 0), (39, 29)])
        mine = AStarPlanner(grid).plan((0, 0), (39, 29))
        self.assertIsNotNone(mine)
        self.assertEqual(mine, other)


class PerfTest(unittest.TestCase):

    def test_large_map_many_queries(self):
        width, height = 500, 400  # 二十万格
        grid = random_map(width, height, density=0.25, seed=2024)
        rng = random.Random(99)
        queries = []
        while len(queries) < 120:
            a = (rng.randrange(width), rng.randrange(height))
            b = (rng.randrange(width), rng.randrange(height))
            if a == b:
                continue
            if not grid.passable(*a) or not grid.passable(*b):
                continue
            queries.append((a, b))
        planner = AStarPlanner(grid)
        started = time.perf_counter()
        reached = 0
        for a, b in queries:
            path = planner.plan(a, b)
            if path is None:
                continue
            reached += 1
            validate_path(grid, path)
        elapsed = time.perf_counter() - started
        self.assertGreater(reached, 100)
        self.assertLess(elapsed, 15.0,
                        "120 次查询耗时 %.2fs，超出秒级预算" % elapsed)


if __name__ == "__main__":
    unittest.main()
