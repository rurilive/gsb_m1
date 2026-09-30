"""范围查询与最近邻查询现有行为的锁定测试（基线，一字不改）。"""

import unittest

from kdtree.scan import inf_norm_sq, nearest, points_in_box


class TestPointsInBox(unittest.TestCase):
    def test_basic_hits(self):
        pts = [(0, 0), (3, 4), (7, 1), (2, 9), (5, 5), (8, 8)]
        self.assertEqual(points_in_box(pts, ((1, 1), (6, 6))), [1, 4])

    def test_box_bounds_are_inclusive(self):
        pts = [(1, 1), (2, 2), (0, 0), (3, 3)]
        self.assertEqual(points_in_box(pts, ((1, 1), (2, 2))), [0, 1])

    def test_equals_bounds_covered(self):
        pts = [(1, 1), (2, 2)]
        self.assertEqual(points_in_box(pts, ((2, 2), (2, 2))), [1])

    def test_all_inside(self):
        pts = [(0, 0), (1, 1), (2, 2)]
        self.assertEqual(points_in_box(pts, ((0, 0), (2, 2))), [0, 1, 2])

    def test_none_inside(self):
        pts = [(0, 0), (10, 10)]
        self.assertEqual(points_in_box(pts, ((3, 3), (4, 4))), [])

    def test_empty_points(self):
        self.assertEqual(points_in_box([], ((0, 0), (1, 1))), [])
        self.assertEqual(points_in_box([], ((0, 0, 0), (1, 1, 1))), [])

    def test_higher_dimension(self):
        pts = [(0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3)]
        self.assertEqual(points_in_box(pts, ((1, 1, 1), (2, 2, 2))), [1, 2])

    def test_single_point(self):
        self.assertEqual(points_in_box([(5, 5)], ((0, 0), (10, 10))), [0])
        self.assertEqual(points_in_box([(5, 5)], ((6, 6), (10, 10))), [])

    def test_duplicate_points(self):
        pts = [(1, 1), (1, 1), (2, 2)]
        self.assertEqual(points_in_box(pts, ((1, 1), (1, 1))), [0, 1])


class TestNearest(unittest.TestCase):
    def test_basic(self):
        pts = [(0, 0), (3, 4), (7, 1), (2, 9), (5, 5), (8, 8)]
        self.assertEqual(nearest(pts, (6, 6)), (4, 2))
        self.assertEqual(nearest(pts, (0, 0)), (0, 0))

    def test_tie_breaks_on_smallest_index(self):
        pts = [(10, 0), (0, 10), (-10, 0), (0, -10)]
        self.assertEqual(nearest(pts, (0, 0)), (0, 100))

    def test_empty_points(self):
        self.assertIsNone(nearest([], (0, 0)))

    def test_single_point(self):
        self.assertEqual(nearest([(2, 3)], (0, 0)), (0, 13))

    def test_exact_hit(self):
        pts = [(1, 1), (2, 2), (3, 3)]
        self.assertEqual(nearest(pts, (2, 2)), (1, 0))

    def test_all_identical(self):
        pts = [(4, 4), (4, 4), (4, 4)]
        self.assertEqual(nearest(pts, (0, 0)), (0, 32))

    def test_higher_dimension(self):
        pts = [(0, 0, 0), (5, 5, 5), (1, 1, 1)]
        self.assertEqual(nearest(pts, (2, 2, 2)), (2, 3))


class TestInfNormSq(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(inf_norm_sq((0, 0), (3, 4)), 25)
        self.assertEqual(inf_norm_sq((1, 1, 1), (1, 1, 1)), 0)

    def test_is_symmetric(self):
        self.assertEqual(inf_norm_sq((2, 5), (7, 1)), inf_norm_sq((7, 1), (2, 5)))


if __name__ == "__main__":
    unittest.main()
