"""基线测试：锁住改造前 calipers.calipers.CalipersKit 的现状行为。

这些断言描述的是"当前朴素实现的事实"，不是"最终应当的样子"：
  - convex_hull 枚举每一对点看其余点是否都在一侧，串成环再去共线中间点，
    起点取最左下点，顶点逆时针；
  - closest_pair 与 hull_diameter 枚举点对逐个求距离取极值，平方级；
  - min_width 在凸包每条边的朝向下投影顶点取跨度，再取最小值；
  - max_triangle 枚举全部三元组取面积最大者；
  - circumcircle 枚举点对与三元组，取包住全部点且半径最小者；
  - contains 判断某点是否落在凸包内部或边界上；
  - min_area_rect 枚举凸包每条边当朝向，逐点投影求轴对齐包围盒。

改造时本文件一字不得修改，且必须保持全绿。
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calipers.calipers import (  # noqa: E402
    CalipersKit,
    CalipersErro,
    PointSetErro,
    ClipErro,
)


SQUARE = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
AXIS_RECT = [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (0.0, 1.0)]
TRIANGLE = [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)]


def _ccw_area2(ring):
    total = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total


class TestConvexHullBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_square_hull_is_four_corners(self):
        hull = self.k.convex_hull(SQUARE)
        self.assertEqual(len(hull), 4)
        self.assertEqual(sorted(hull), sorted(SQUARE))

    def test_hull_starts_at_lower_left(self):
        # 最左下点：先比纵坐标再比横坐标。
        hull = self.k.convex_hull([(4.0, 0.0), (0.0, 2.0), (1.0, 0.0), (3.0, 3.0)])
        self.assertEqual(hull[0], (1.0, 0.0))

    def test_hull_is_counter_clockwise(self):
        self.assertGreater(_ccw_area2(self.k.convex_hull(SQUARE)), 0.0)

    def test_interior_points_dropped(self):
        pts = SQUARE + [(2.0, 2.0), (1.0, 1.0), (3.0, 2.0)]
        hull = self.k.convex_hull(pts)
        self.assertEqual(len(hull), 4)
        self.assertNotIn((2.0, 2.0), hull)

    def test_duplicate_points_removed(self):
        pts = SQUARE + [(0.0, 0.0), (4.0, 4.0)]
        self.assertEqual(len(self.k.convex_hull(pts)), 4)

    def test_collinear_point_on_edge_dropped(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
        hull = self.k.convex_hull(pts)
        self.assertNotIn((1.0, 0.0), hull)
        self.assertEqual(len(hull), 4)

    def test_single_point(self):
        self.assertEqual(self.k.convex_hull([(1.0, 2.0)]), [(1.0, 2.0)])

    def test_two_points(self):
        hull = self.k.convex_hull([(3.0, 3.0), (0.0, 0.0)])
        self.assertEqual(hull, [(0.0, 0.0), (3.0, 3.0)])

    def test_all_collinear_returns_endpoints(self):
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        self.assertEqual(self.k.convex_hull(pts), [(0.0, 0.0), (3.0, 3.0)])

    def test_all_collinear_vertical(self):
        pts = [(0.0, 3.0), (0.0, 0.0), (0.0, 2.0)]
        self.assertEqual(self.k.convex_hull(pts), [(0.0, 0.0), (0.0, 3.0)])

    def test_every_point_coincident(self):
        self.assertEqual(self.k.convex_hull([(1.0, 1.0), (1.0, 1.0)]),
                         [(1.0, 1.0)])

    def test_empty_point_set_raises(self):
        with self.assertRaises(PointSetErro):
            self.k.convex_hull([])

    def test_empty_is_calipers_erro(self):
        with self.assertRaises(CalipersErro):
            self.k.convex_hull([])

    def test_non_finite_coordinate_raises(self):
        with self.assertRaises(PointSetErro):
            self.k.convex_hull([(0.0, 0.0), (float("nan"), 1.0)])

    def test_counts_positive(self):
        self.k.convex_hull(SQUARE)
        self.assertGreater(self.k.hull_pairs, 0)
        self.assertGreater(self.k.hull_checks, 0)


class TestClosestPairBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_square_closest_is_side(self):
        d2, pair = self.k.closest_pair(SQUARE)
        self.assertEqual(d2, 16.0)
        self.assertEqual(pair, ((0.0, 0.0), (0.0, 4.0)))

    def test_closest_with_duplicate_is_zero(self):
        pts = [(0.0, 0.0), (3.0, 3.0), (0.0, 0.0)]
        d2, pair = self.k.closest_pair(pts)
        self.assertEqual(d2, 0.0)
        self.assertEqual(pair, ((0.0, 0.0), (0.0, 0.0)))

    def test_closest_single_point(self):
        d2, pair = self.k.closest_pair([(2.0, 5.0)])
        self.assertEqual(d2, 0.0)
        self.assertEqual(pair, ((2.0, 5.0), (2.0, 5.0)))

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.closest_pair([])

    def test_pairs_count_matches_combination(self):
        self.k.closest_pair(SQUARE)
        self.assertEqual(self.k.closest_pairs, 6)


class TestHullDiameterBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_square_diameter_is_diagonal(self):
        d2, pair = self.k.hull_diameter(SQUARE)
        self.assertEqual(d2, 32.0)
        self.assertEqual(pair, ((0.0, 0.0), (4.0, 4.0)))

    def test_triangle_diameter(self):
        d2, pair = self.k.hull_diameter(TRIANGLE)
        self.assertEqual(d2, 32.0)
        self.assertEqual(pair, ((0.0, 4.0), (4.0, 0.0)))

    def test_interior_point_not_diameter_end(self):
        pts = SQUARE + [(2.0, 2.0)]
        d2, pair = self.k.hull_diameter(pts)
        self.assertNotIn((2.0, 2.0), pair)

    def test_all_collinear_diameter_is_span(self):
        d2, pair = self.k.hull_diameter([(0.0, 0.0), (2.0, 0.0), (5.0, 0.0)])
        self.assertEqual(d2, 25.0)
        self.assertEqual(pair, ((0.0, 0.0), (5.0, 0.0)))

    def test_single_point_zero(self):
        d2, pair = self.k.hull_diameter([(2.0, 5.0)])
        self.assertEqual(d2, 0.0)
        self.assertEqual(pair, ((2.0, 5.0), (2.0, 5.0)))

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.hull_diameter([])

    def test_pairs_count_matches_hull_vertices(self):
        self.k.hull_diameter(SQUARE)
        self.assertEqual(self.k.diameter_pairs, 6)


class TestMinWidthBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_square_width(self):
        self.assertAlmostEqual(self.k.min_width(SQUARE), 4.0)

    def test_axis_rect_width(self):
        self.assertAlmostEqual(self.k.min_width(AXIS_RECT), 1.0)

    def test_all_collinear_width_zero(self):
        self.assertEqual(self.k.min_width([(0.0, 0.0), (2.0, 0.0), (5.0, 0.0)]), 0.0)

    def test_two_points_width_zero(self):
        self.assertEqual(self.k.min_width([(0.0, 0.0), (3.0, 4.0)]), 0.0)

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.min_width([])


class TestMaxTriangleBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_triangle_area(self):
        area, tri = self.k.max_triangle(TRIANGLE)
        self.assertAlmostEqual(area, 8.0)
        self.assertEqual(tri, ((0.0, 0.0), (0.0, 4.0), (4.0, 0.0)))

    def test_square_max_triangle_is_half(self):
        area, tri = self.k.max_triangle(SQUARE)
        self.assertAlmostEqual(area, 8.0)
        self.assertEqual(len(tri), 3)

    def test_collinear_zero_area(self):
        area, tri = self.k.max_triangle([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
        self.assertEqual(area, 0.0)

    def test_two_points_degenerate(self):
        area, tri = self.k.max_triangle([(0.0, 0.0), (1.0, 1.0)])
        self.assertEqual(area, 0.0)
        self.assertEqual(tri[0], tri[1])

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.max_triangle([])

    def test_triple_count_positive(self):
        self.k.max_triangle(SQUARE)
        self.assertEqual(self.k.triangle_ops, 4)


class TestCircumcircleBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_square_circle(self):
        c = self.k.circumcircle(SQUARE)
        self.assertAlmostEqual(c["radius"], math.sqrt(8.0))
        self.assertEqual(c["center"], (2.0, 2.0))

    def test_right_triangle_circle(self):
        # 直角三角形的最小包围圆以斜边为直径。
        c = self.k.circumcircle(TRIANGLE)
        self.assertAlmostEqual(c["radius"], math.sqrt(8.0))
        self.assertEqual(c["center"], (2.0, 2.0))

    def test_collinear_circle_is_span(self):
        c = self.k.circumcircle([(0.0, 0.0), (2.0, 0.0), (5.0, 0.0)])
        self.assertAlmostEqual(c["radius"], 2.5)
        self.assertEqual(c["center"], (2.5, 0.0))

    def test_single_point_zero_radius(self):
        c = self.k.circumcircle([(2.0, 5.0)])
        self.assertEqual(c["radius"], 0.0)
        self.assertEqual(c["center"], (2.0, 5.0))

    def test_circle_covers_all_points(self):
        pts = SQUARE + [(3.0, 1.0), (1.0, 3.0)]
        c = self.k.circumcircle(pts)
        for p in pts:
            d = math.hypot(p[0] - c["center"][0], p[1] - c["center"][1])
            self.assertLessEqual(d, c["radius"] + 1e-9)

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.circumcircle([])


class TestContainsBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_interior_point_contained(self):
        self.assertTrue(self.k.contains(SQUARE, (2.0, 2.0)))

    def test_boundary_point_contained(self):
        self.assertTrue(self.k.contains(SQUARE, (4.0, 2.0)))

    def test_vertex_contained(self):
        self.assertTrue(self.k.contains(SQUARE, (0.0, 0.0)))

    def test_outside_point_rejected(self):
        self.assertFalse(self.k.contains(SQUARE, (5.0, 5.0)))

    def test_single_point_hull(self):
        self.assertTrue(self.k.contains([(1.0, 1.0)], (1.0, 1.0)))
        self.assertFalse(self.k.contains([(1.0, 1.0)], (2.0, 2.0)))

    def test_segment_hull(self):
        seg = [(0.0, 0.0), (4.0, 0.0)]
        self.assertTrue(self.k.contains(seg, (2.0, 0.0)))
        self.assertFalse(self.k.contains(seg, (2.0, 1.0)))

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.contains([], (0.0, 0.0))


class TestMinAreaRectBaseline(unittest.TestCase):
    def setUp(self):
        self.k = CalipersKit()

    def test_square_rect(self):
        rect = self.k.min_area_rect(SQUARE)
        self.assertAlmostEqual(rect["area"], 16.0)
        self.assertEqual(len(rect["corners"]), 4)

    def test_axis_rect_area(self):
        rect = self.k.min_area_rect(AXIS_RECT)
        self.assertAlmostEqual(rect["area"], 4.0)

    def test_rotated_rect_recovers_area(self):
        c = math.cos(math.radians(30.0))
        s = math.sin(math.radians(30.0))
        pts = [(round(x * c - y * s, 9), round(x * s + y * c, 9))
               for x, y in AXIS_RECT]
        rect = self.k.min_area_rect(pts)
        self.assertAlmostEqual(rect["area"], 4.0, places=6)

    def test_two_points_area_zero(self):
        rect = self.k.min_area_rect([(0.0, 0.0), (3.0, 4.0)])
        self.assertEqual(rect["area"], 0.0)

    def test_collinear_area_zero(self):
        rect = self.k.min_area_rect([(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)])
        self.assertEqual(rect["area"], 0.0)

    def test_single_point_area_zero(self):
        rect = self.k.min_area_rect([(2.0, 5.0)])
        self.assertEqual(rect["area"], 0.0)
        self.assertEqual(rect["corners"], [(2.0, 5.0)] * 4)

    def test_empty_raises(self):
        with self.assertRaises(CalipersErro):
            self.k.min_area_rect([])

    def test_edge_count_matches_hull(self):
        self.k.min_area_rect(SQUARE)
        self.assertEqual(self.k.rect_edges, 4)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        pts = [(0.0, 0.0), (3.0, 1.0), (1.0, 4.0), (5.0, 2.0), (2.0, 2.0)]
        k1 = CalipersKit()
        k2 = CalipersKit()
        self.assertEqual(k1.convex_hull(pts), k2.convex_hull(pts))
        self.assertEqual(k1.closest_pair(pts), k2.closest_pair(pts))
        self.assertEqual(k1.hull_diameter(pts), k2.hull_diameter(pts))
        self.assertEqual(k1.max_triangle(pts), k2.max_triangle(pts))
        self.assertEqual(k1.circumcircle(pts), k2.circumcircle(pts))
        self.assertEqual(k1.min_area_rect(pts), k2.min_area_rect(pts))

    def test_counts_reset_between_calls(self):
        k = CalipersKit()
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 2.0)]
        k.hull_diameter(pts)
        first = k.diameter_pairs
        k.hull_diameter(pts)
        self.assertEqual(k.diameter_pairs, first)

    def test_closest_pairs_reset(self):
        k = CalipersKit()
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 2.0)]
        k.closest_pair(pts)
        first = k.closest_pairs
        k.closest_pair(pts)
        self.assertEqual(k.closest_pairs, first)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(PointSetErro, CalipersErro))
        self.assertTrue(issubclass(ClipErro, CalipersErro))
        self.assertTrue(issubclass(CalipersErro, Exception))


if __name__ == "__main__":
    unittest.main()
