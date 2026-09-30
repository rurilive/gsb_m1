"""基线测试：锁住改造前 hullx.hull.HullKit 的现状行为。

这些断言描述的是"当前朴素实现的事实"，不是"最终应当的样子"：
  - convex_hull 枚举每一对点看其余点是否都在一侧，再串成环并去共线中间点；
  - diameter 在凸包顶点上两两配对全部比一遍，平局取顶点下标字典序最小的一对；
  - min_bounding_rect 枚举全部顶点对当朝向，逐点投影求包围盒，取面积最小者；
  - width 取最小外接矩形里最小的法向跨度。

改造时本文件一字不得修改，且必须保持全绿。
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hullx.hull import (  # noqa: E402
    HullKit,
    HullErro,
    PointSetErro,
    RectErro,
)


SQUARE = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
AXIS_RECT = [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (0.0, 1.0)]


def _rotate(pts, deg):
    c = math.cos(math.radians(deg))
    s = math.sin(math.radians(deg))
    return [(round(x * c - y * s, 9), round(x * s + y * c, 9)) for x, y in pts]


class TestConvexHullBaseline(unittest.TestCase):
    def setUp(self):
        self.k = HullKit()

    def test_square_hull_is_four_corners(self):
        hull = self.k.convex_hull(SQUARE)
        self.assertEqual(len(hull), 4)
        self.assertEqual(sorted(hull), sorted(SQUARE))

    def test_hull_starts_at_smallest_point(self):
        hull = self.k.convex_hull(SQUARE)
        self.assertEqual(hull[0], (0.0, 0.0))

    def test_hull_is_counter_clockwise(self):
        hull = self.k.convex_hull(SQUARE)
        area2 = 0.0
        n = len(hull)
        for i in range(n):
            x1, y1 = hull[i]
            x2, y2 = hull[(i + 1) % n]
            area2 += x1 * y2 - x2 * y1
        self.assertGreater(area2, 0.0)

    def test_interior_points_dropped(self):
        pts = SQUARE + [(2.0, 2.0), (1.0, 1.0), (3.0, 2.0)]
        hull = self.k.convex_hull(pts)
        self.assertEqual(len(hull), 4)
        self.assertNotIn((2.0, 2.0), hull)

    def test_duplicate_points_removed(self):
        pts = SQUARE + [(0.0, 0.0), (4.0, 4.0)]
        hull = self.k.convex_hull(pts)
        self.assertEqual(len(hull), 4)

    def test_collinear_point_on_edge_dropped(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
        hull = self.k.convex_hull(pts)
        self.assertNotIn((1.0, 0.0), hull)
        self.assertEqual(len(hull), 4)

    def test_single_point(self):
        self.assertEqual(self.k.convex_hull([(1.0, 2.0)]), [(1.0, 2.0)])

    def test_two_points(self):
        hull = self.k.convex_hull([(0.0, 0.0), (3.0, 3.0)])
        self.assertEqual(hull, [(0.0, 0.0), (3.0, 3.0)])

    def test_all_collinear_returns_endpoints(self):
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        hull = self.k.convex_hull(pts)
        self.assertEqual(hull, [(0.0, 0.0), (3.0, 3.0)])

    def test_every_point_coincident(self):
        self.assertEqual(self.k.convex_hull([(1.0, 1.0), (1.0, 1.0)]),
                         [(1.0, 1.0)])

    def test_empty_point_set_raises(self):
        with self.assertRaises(PointSetErro):
            self.k.convex_hull([])

    def test_empty_is_hull_erro(self):
        with self.assertRaises(HullErro):
            self.k.convex_hull([])

    def test_non_finite_coordinate_raises(self):
        with self.assertRaises(PointSetErro):
            self.k.convex_hull([(0.0, 0.0), (float("nan"), 1.0)])

    def test_pairs_count_positive(self):
        self.k.convex_hull(SQUARE)
        self.assertGreater(self.k.hull_pairs, 0)
        self.assertGreater(self.k.hull_side_checks, 0)


class TestDiameterBaseline(unittest.TestCase):
    def setUp(self):
        self.k = HullKit()

    def test_square_diameter_is_diagonal(self):
        d, pair = self.k.diameter(SQUARE)
        self.assertAlmostEqual(d, math.sqrt(32.0))
        self.assertEqual(sorted(pair), [(0.0, 0.0), (4.0, 4.0)])

    def test_triangle_diameter(self):
        d, pair = self.k.diameter([(0.0, 0.0), (3.0, 0.0), (0.0, 4.0)])
        self.assertEqual(d, 5.0)
        self.assertEqual(sorted(pair), [(0.0, 4.0), (3.0, 0.0)])

    def test_interior_point_does_not_be_diameter_end(self):
        pts = SQUARE + [(2.0, 2.0)]
        d, pair = self.k.diameter(pts)
        self.assertNotIn((2.0, 2.0), pair)

    def test_all_collinear_diameter_is_span(self):
        d, pair = self.k.diameter([(0.0, 0.0), (2.0, 0.0), (5.0, 0.0)])
        self.assertEqual(d, 5.0)
        self.assertEqual(sorted(pair), [(0.0, 0.0), (5.0, 0.0)])

    def test_single_point_zero_diameter(self):
        d, pair = self.k.diameter([(2.0, 5.0)])
        self.assertEqual(d, 0.0)
        self.assertEqual(pair, ((2.0, 5.0), (2.0, 5.0)))

    def test_empty_raises(self):
        with self.assertRaises(HullErro):
            self.k.diameter([])

    def test_pairs_count_matches_hull_vertices(self):
        self.k.diameter(SQUARE)
        self.assertEqual(self.k.diameter_pairs, 6)


class TestMinBoundingRectBaseline(unittest.TestCase):
    def setUp(self):
        self.k = HullKit()

    def test_square_rect(self):
        rect = self.k.min_bounding_rect(SQUARE)
        self.assertAlmostEqual(rect["area"], 16.0)
        self.assertAlmostEqual(rect["width"], 4.0)
        self.assertAlmostEqual(rect["height"], 4.0)
        self.assertEqual(len(rect["corners"]), 4)

    def test_axis_rect_area_and_angle(self):
        rect = self.k.min_bounding_rect(AXIS_RECT)
        self.assertAlmostEqual(rect["area"], 4.0)
        self.assertAlmostEqual(rect["width"] * rect["height"], rect["area"])
        self.assertAlmostEqual(rect["angle"], 0.0)

    def test_rotated_rect_recovers_area(self):
        rect = self.k.min_bounding_rect(_rotate(AXIS_RECT, 30.0))
        self.assertAlmostEqual(rect["area"], 4.0, places=6)

    def test_two_points_area_zero(self):
        rect = self.k.min_bounding_rect([(0.0, 0.0), (3.0, 4.0)])
        self.assertEqual(rect["area"], 0.0)
        self.assertAlmostEqual(rect["width"], 5.0)
        self.assertEqual(rect["height"], 0.0)

    def test_all_collinear_area_zero(self):
        rect = self.k.min_bounding_rect([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
        self.assertEqual(rect["area"], 0.0)
        self.assertEqual(rect["height"], 0.0)

    def test_single_point_area_zero(self):
        rect = self.k.min_bounding_rect([(2.0, 5.0)])
        self.assertEqual(rect["area"], 0.0)
        self.assertEqual(rect["corners"], [(2.0, 5.0)] * 4)

    def test_empty_raises(self):
        with self.assertRaises(HullErro):
            self.k.min_bounding_rect([])

    def test_point_checks_positive(self):
        self.k.min_bounding_rect(AXIS_RECT)
        self.assertGreater(self.k.rect_pairs, 0)
        self.assertGreater(self.k.rect_point_checks, 0)


class TestWidthBaseline(unittest.TestCase):
    def setUp(self):
        self.k = HullKit()

    def test_square_width(self):
        self.assertAlmostEqual(self.k.width(SQUARE), 4.0)

    def test_axis_rect_width(self):
        self.assertAlmostEqual(self.k.width(AXIS_RECT), 1.0)

    def test_all_collinear_width_zero(self):
        self.assertEqual(
            self.k.width([(0.0, 0.0), (2.0, 0.0), (5.0, 0.0)]), 0.0)

    def test_empty_raises(self):
        with self.assertRaises(HullErro):
            self.k.width([])


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        pts = [(0.0, 0.0), (3.0, 1.0), (1.0, 4.0), (5.0, 2.0), (2.0, 2.0)]
        k1 = HullKit()
        k2 = HullKit()
        self.assertEqual(k1.convex_hull(pts), k2.convex_hull(pts))
        self.assertEqual(k1.diameter(pts), k2.diameter(pts))
        self.assertEqual(k1.min_bounding_rect(pts), k2.min_bounding_rect(pts))

    def test_counts_reset_between_calls(self):
        k = HullKit()
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 2.0)]
        k.diameter(pts)
        first = k.diameter_pairs
        k.diameter(pts)
        self.assertEqual(k.diameter_pairs, first)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(PointSetErro, HullErro))
        self.assertTrue(issubclass(RectErro, HullErro))
        self.assertTrue(issubclass(HullErro, Exception))


if __name__ == "__main__":
    unittest.main()
