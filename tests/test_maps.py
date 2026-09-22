"""地图构造器的行为基线：可复现、密度与强制留空。"""

import unittest

from gridnav import Grid, open_map, pillared_map, random_map


class OpenMapTest(unittest.TestCase):

    def test_no_obstacles(self):
        grid = open_map(6, 5)
        self.assertIsInstance(grid, Grid)
        self.assertEqual(grid.blocked_cells(), ())
        for y in range(5):
            for x in range(6):
                self.assertTrue(grid.passable(x, y))


class RandomMapTest(unittest.TestCase):

    def test_same_seed_same_map(self):
        first = random_map(12, 9, density=0.35, seed=42)
        second = random_map(12, 9, density=0.35, seed=42)
        self.assertEqual(first.blocked_cells(), second.blocked_cells())

    def test_different_seed_differs(self):
        first = random_map(12, 9, density=0.35, seed=42)
        second = random_map(12, 9, density=0.35, seed=43)
        self.assertNotEqual(first.blocked_cells(), second.blocked_cells())

    def test_density_zero_is_open(self):
        self.assertEqual(random_map(8, 8, density=0.0, seed=1).blocked_cells(), ())

    def test_density_one_blocks_everything_but_protected(self):
        grid = random_map(5, 5, density=1.0, seed=1,
                          protected=[(0, 0), (4, 4)])
        self.assertFalse(grid.is_blocked(0, 0))
        self.assertFalse(grid.is_blocked(4, 4))
        self.assertTrue(grid.is_blocked(2, 2))
        self.assertEqual(len(grid.blocked_cells()), 23)

    def test_density_bounds_are_rough(self):
        grid = random_map(40, 40, density=0.3, seed=9)
        self.assertLess(0.2, len(grid.blocked_cells()) / (40 * 40))
        self.assertLess(len(grid.blocked_cells()) / (40 * 40), 0.4)

    def test_protected_cells_stay_open(self):
        grid = random_map(10, 10, density=0.9, seed=2,
                          protected=[(1, 1), (8, 8)])
        self.assertTrue(grid.passable(1, 1))
        self.assertTrue(grid.passable(8, 8))


class PillaredMapTest(unittest.TestCase):

    def test_pillars_on_stride(self):
        grid = pillared_map(9, 8, stride=3)
        self.assertEqual(grid.blocked_cells(), ((2, 2), (2, 5), (5, 2), (5, 5), (8, 2), (8, 5)))

    def test_default_stride_matches_four(self):
        self.assertEqual(pillared_map(7, 7).blocked_cells(),
                         pillared_map(7, 7, stride=4).blocked_cells())


if __name__ == "__main__":
    unittest.main()
