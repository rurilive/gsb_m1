"""基线测试：锁住改造前 geox.geom.PlanarGeom 的现状行为。

这些断言描述的是"当前朴素实现的事实"，不是"最终应当的样子"：
  - convex_hull 用逐点暴力扫描，无去重以外的优化；
  - closest_pair 用两两配对全比一遍，平局取下标字典序最小的一对；
  - segments_intersect 用参数方程加共线投影判断；
  - point_in_polygon 用逐边射线法，边界与顶点判为在内。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geox.geom import (  # noqa: E402
    PlanarGeom,
    GeomError,
    PointSetError,
    PolygonError,
)


SQUARE = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]


class TestConvexHullBaseline(unittest.TestCase):
    def setUp(self):
        self.g = PlanarGeom()

    def test_square_hull_is_four_corners(self):
        hull = self.g.convex_hull(SQUARE)
        self.assertEqual(len(hull), 4)
        self.assertEqual(sorted(hull), sorted(SQUARE))

    def test_hull_is_counter_clockwise(self):
        hull = self.g.convex_hull(SQUARE)
        self.assertEqual(hull[0], (0.0, 0.0))

    def test_interior_points_dropped(self):
        pts = SQUARE + [(2.0, 2.0), (1.0, 1.0), (3.0, 2.0)]
        hull = self.g.convex_hull(pts)
        self.assertEqual(len(hull), 4)
        self.assertNotIn((2.0, 2.0), hull)

    def test_duplicate_points_removed(self):
        pts = SQUARE + [(0.0, 0.0), (4.0, 4.0)]
        hull = self.g.convex_hull(pts)
        self.assertEqual(len(hull), 4)

    def test_single_point(self):
        self.assertEqual(self.g.convex_hull([(1.0, 2.0)]), [(1.0, 2.0)])

    def test_two_points(self):
        hull = self.g.convex_hull([(0.0, 0.0), (3.0, 3.0)])
        self.assertEqual(hull, [(0.0, 0.0), (3.0, 3.0)])

    def test_all_collinear_returns_endpoints(self):
        pts = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        hull = self.g.convex_hull(pts)
        self.assertEqual(hull, [(0.0, 0.0), (3.0, 3.0)])

    def test_empty_point_set_raises(self):
        with self.assertRaises(PointSetError):
            self.g.convex_hull([])

    def test_error_is_geom_error(self):
        with self.assertRaises(GeomError):
            self.g.convex_hull([])

    def test_hull_comparisons_are_quadratic_on_square(self):
        self.g.convex_hull(SQUARE)
        self.assertGreater(self.g.hull_comparisons, 0)


class TestClosestPairBaseline(unittest.TestCase):
    def setUp(self):
        self.g = PlanarGeom()

    def test_simple_closest_pair(self):
        pts = [(0.0, 0.0), (5.0, 0.0), (1.0, 0.0)]
        d, pair = self.g.closest_pair(pts)
        self.assertEqual(d, 1.0)
        self.assertEqual(sorted(pair), [(0.0, 0.0), (1.0, 0.0)])

    def test_coincident_points_give_zero(self):
        pts = [(0.0, 0.0), (2.0, 2.0), (0.0, 0.0)]
        d, pair = self.g.closest_pair(pts)
        self.assertEqual(d, 0.0)

    def test_tie_keeps_first_index_pair(self):
        # (0,0)-(1,0) 与 (1,0)-(2,0) 距离相同，取下标字典序最小的一对
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        d, pair = self.g.closest_pair(pts)
        self.assertEqual(d, 1.0)
        self.assertEqual(sorted(pair), [(0.0, 0.0), (1.0, 0.0)])

    def test_too_few_points_raises(self):
        with self.assertRaises(PointSetError):
            self.g.closest_pair([(1.0, 1.0)])

    def test_comparisons_count_all_pairs(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
        self.g.closest_pair(pts)
        self.assertEqual(self.g.closest_comparisons, 6)


class TestSegmentIntersectionBaseline(unittest.TestCase):
    def setUp(self):
        self.g = PlanarGeom()

    def test_crossing_segments_intersect(self):
        self.assertTrue(self.g.segments_intersect(
            (0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)))

    def test_disjoint_segments(self):
        self.assertFalse(self.g.segments_intersect(
            (0.0, 0.0), (1.0, 0.0), (5.0, 5.0), (6.0, 6.0)))

    def test_parallel_not_collinear(self):
        self.assertFalse(self.g.segments_intersect(
            (0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)))

    def test_collinear_overlapping(self):
        self.assertTrue(self.g.segments_intersect(
            (0.0, 0.0), (3.0, 0.0), (1.0, 0.0), (5.0, 0.0)))

    def test_collinear_touching_at_endpoint(self):
        self.assertTrue(self.g.segments_intersect(
            (0.0, 0.0), (2.0, 0.0), (2.0, 0.0), (4.0, 0.0)))

    def test_collinear_disjoint(self):
        self.assertFalse(self.g.segments_intersect(
            (0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)))

    def test_identical_segments(self):
        self.assertTrue(self.g.segments_intersect(
            (0.0, 0.0), (2.0, 2.0), (0.0, 0.0), (2.0, 2.0)))

    def test_shared_endpoint(self):
        self.assertTrue(self.g.segments_intersect(
            (0.0, 0.0), (1.0, 1.0), (1.0, 1.0), (2.0, 0.0)))

    def test_touching_only_at_inner_point_of_one(self):
        self.assertTrue(self.g.segments_intersect(
            (0.0, 0.0), (4.0, 0.0), (2.0, 0.0), (2.0, 2.0)))


class TestPointInPolygonBaseline(unittest.TestCase):
    def setUp(self):
        self.g = PlanarGeom()

    def test_interior_point(self):
        self.assertTrue(self.g.point_in_polygon((2.0, 2.0), SQUARE))

    def test_exterior_point(self):
        self.assertFalse(self.g.point_in_polygon((5.0, 2.0), SQUARE))

    def test_point_on_edge(self):
        self.assertTrue(self.g.point_in_polygon((2.0, 0.0), SQUARE))

    def test_point_on_vertex(self):
        self.assertTrue(self.g.point_in_polygon((4.0, 4.0), SQUARE))

    def test_point_below_polygon(self):
        self.assertFalse(self.g.point_in_polygon((2.0, -1.0), SQUARE))

    def test_triangle(self):
        tri = [(0.0, 0.0), (4.0, 0.0), (0.0, 4.0)]
        self.assertTrue(self.g.point_in_polygon((1.0, 1.0), tri))
        self.assertFalse(self.g.point_in_polygon((3.0, 3.0), tri))

    def test_too_few_vertices_raises(self):
        with self.assertRaises(PolygonError):
            self.g.point_in_polygon((0.0, 0.0), [(0.0, 0.0), (1.0, 1.0)])

    def test_polygon_error_is_geom_error(self):
        with self.assertRaises(GeomError):
            self.g.point_in_polygon((0.0, 0.0), [])


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        pts = [(0.0, 0.0), (3.0, 1.0), (1.0, 4.0), (5.0, 2.0), (2.0, 2.0)]
        g1 = PlanarGeom()
        g2 = PlanarGeom()
        self.assertEqual(g1.convex_hull(pts), g2.convex_hull(pts))
        self.assertEqual(g1.closest_pair(pts), g2.closest_pair(pts))

    def test_counts_reset_between_calls(self):
        g = PlanarGeom()
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        g.closest_pair(pts)
        first = g.closest_comparisons
        g.closest_pair(pts)
        self.assertEqual(g.closest_comparisons, first)


if __name__ == "__main__":
    unittest.main()
