"""半平面交现有行为的锁定测试（基线，一字不改）。"""

import unittest
from fractions import Fraction

from halfplane.hpi import (
    HalfPlane,
    intersect,
    line_intersection,
    polygon_area,
)


def square_halfplanes():
    """单位正方形 [0,1]x[0,1]，取四条内向半平面。"""
    return [
        HalfPlane((0, 0), (1, 0)),
        HalfPlane((1, 0), (1, 1)),
        HalfPlane((1, 1), (0, 1)),
        HalfPlane((0, 1), (0, 0)),
    ]


class TestHalfPlane(unittest.TestCase):
    def test_contains_inner_point(self):
        hp = HalfPlane((0, 0), (1, 0))
        self.assertTrue(hp.contains((0, 1)))

    def test_contains_boundary_point(self):
        hp = HalfPlane((0, 0), (1, 0))
        self.assertTrue(hp.contains((2, 0)))

    def test_rejects_outer_point(self):
        hp = HalfPlane((0, 0), (1, 0))
        self.assertFalse(hp.contains((0, -1)))

    def test_rejects_degenerate_line(self):
        with self.assertRaises(ValueError):
            HalfPlane((1, 1), (1, 1))


class TestLineIntersection(unittest.TestCase):
    def test_crossing_lines(self):
        h1 = HalfPlane((0, 0), (1, 0))
        h2 = HalfPlane((0, 0), (0, 1))
        self.assertEqual(line_intersection(h1, h2), (Fraction(0), Fraction(0)))

    def test_parallel_lines_return_none(self):
        h1 = HalfPlane((0, 0), (1, 0))
        h2 = HalfPlane((0, 1), (1, 1))
        self.assertIsNone(line_intersection(h1, h2))


class TestPolygonArea(unittest.TestCase):
    def test_unit_square(self):
        verts = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.assertEqual(polygon_area(verts), Fraction(1))

    def test_degenerate_is_zero(self):
        self.assertEqual(polygon_area([(0, 0), (1, 1)]), Fraction(0))


class TestIntersect(unittest.TestCase):
    def test_unit_square_region(self):
        res = intersect(square_halfplanes())
        self.assertEqual(res.area, Fraction(1))
        self.assertEqual(len(res.vertices), 4)
        for p in [(0, 0), (1, 0), (1, 1), (0, 1)]:
            self.assertIn((Fraction(p[0]), Fraction(p[1])), res.vertices)

    def test_vertices_are_ccw(self):
        res = intersect(square_halfplanes())
        verts = res.vertices
        n = len(verts)
        for i in range(n):
            o = verts[i]
            a = verts[(i + 1) % n]
            b = verts[(i + 2) % n]
            cross = (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
            self.assertGreater(cross, 0)

    def test_result_equal_by_value(self):
        r1 = intersect(square_halfplanes())
        r2 = intersect(square_halfplanes())
        self.assertEqual(r1, r2)

    def test_axis_aligned_triangle(self):
        hps = [
            HalfPlane((0, 0), (2, 0)),
            HalfPlane((2, 0), (0, 2)),
            HalfPlane((0, 2), (0, 0)),
        ]
        res = intersect(hps)
        self.assertEqual(res.area, Fraction(2))

    def test_parallelogram_area(self):
        hps = [
            HalfPlane((0, 0), (2, 1)),
            HalfPlane((2, 1), (1, 2)),
            HalfPlane((1, 2), (-1, 1)),
            HalfPlane((-1, 1), (0, 0)),
        ]
        res = intersect(hps)
        self.assertEqual(res.area, Fraction(3))


if __name__ == "__main__":
    unittest.main()
