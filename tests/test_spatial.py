"""基线测试：锁住 FlatIndex 的现有线性扫描行为。

这些用例描述的是改造前的事实，一个字都不许改，新增行为请另开文件。
"""

import unittest

from geolib.spatial import GeoError, RectError, FlatIndex, rect_of


def build():
    idx = FlatIndex()
    idx.insert((0.0, 0.0, 1.0, 1.0), "a")
    idx.insert((2.0, 2.0, 4.0, 4.0), "b")
    idx.insert((0.5, 0.5, 3.0, 3.0), "c")
    return idx


class TestRectOf(unittest.TestCase):
    def test_returns_four_floats(self):
        self.assertEqual(rect_of((0, 0, 2, 3)), (0.0, 0.0, 2.0, 3.0))

    def test_lower_greater_than_upper_raises(self):
        with self.assertRaises(RectError):
            rect_of((3.0, 0.0, 1.0, 2.0))

    def test_rect_error_is_geo_error(self):
        self.assertTrue(issubclass(RectError, GeoError))


class TestLengthAndNames(unittest.TestCase):
    def test_len_and_count(self):
        idx = build()
        self.assertEqual(len(idx), 3)
        self.assertEqual(idx.count(), 3)

    def test_names_in_insertion_order(self):
        self.assertEqual(build().names(), ["a", "b", "c"])

    def test_items_are_copies(self):
        items = build().items()
        self.assertEqual(items[0], ((0.0, 0.0, 1.0, 1.0), "a"))
        self.assertEqual(len(items), 3)


class TestInsertRemove(unittest.TestCase):
    def test_insert_returns_name(self):
        idx = FlatIndex()
        self.assertEqual(idx.insert((0.0, 0.0, 1.0, 1.0), "x"), "x")

    def test_insert_bad_rect_raises(self):
        with self.assertRaises(RectError):
            FlatIndex().insert((2.0, 0.0, 1.0, 1.0), "bad")

    def test_remove_returns_rect(self):
        idx = build()
        got = idx.remove("b")
        self.assertEqual(got, (2.0, 2.0, 4.0, 4.0))
        self.assertEqual(idx.names(), ["a", "c"])

    def test_remove_missing_raises(self):
        with self.assertRaises(GeoError):
            build().remove("nope")


class TestContainsPoint(unittest.TestCase):
    def test_hits_in_insertion_order(self):
        self.assertEqual(build().contains_point(0.75, 0.75), ["a", "c"])

    def test_boundary_is_inside(self):
        self.assertEqual(build().contains_point(0.0, 0.0), ["a"])

    def test_miss_returns_empty(self):
        self.assertEqual(build().contains_point(9.0, 9.0), [])

    def test_empty_index(self):
        self.assertEqual(FlatIndex().contains_point(0.0, 0.0), [])


class TestIntersect(unittest.TestCase):
    def test_overlap_hits(self):
        self.assertEqual(build().intersect((2.5, 2.5, 3.5, 3.5)), ["b", "c"])

    def test_touching_edges_count(self):
        self.assertEqual(build().intersect((1.0, 1.0, 2.0, 2.0)), ["a", "b", "c"])

    def test_disjoint_returns_empty(self):
        self.assertEqual(build().intersect((10.0, 10.0, 11.0, 11.0)), [])

    def test_degenerate_point_query(self):
        self.assertEqual(build().intersect((0.0, 0.0, 0.0, 0.0)), ["a"])


class TestNearest(unittest.TestCase):
    def test_nearest_picks_closest(self):
        self.assertEqual(build().nearest(-1.0, -1.0), "a")

    def test_nearest_inside_returns_containing(self):
        self.assertEqual(build().nearest(3.5, 3.5), "b")

    def test_nearest_tie_prefers_earlier_insert(self):
        idx = FlatIndex()
        idx.insert((0.0, 0.0, 1.0, 1.0), "first")
        idx.insert((4.0, 0.0, 5.0, 1.0), "second")
        self.assertEqual(idx.nearest(2.5, 0.5), "first")

    def test_nearest_empty_returns_none(self):
        self.assertIsNone(FlatIndex().nearest(0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
