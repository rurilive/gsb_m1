"""PointIndex 既有行为锁定。"""

import unittest

from geogrid.errors import DuplicateId, InvalidCoordinate, UnknownId
from geogrid.index import PointIndex


class AddAndAtTest(unittest.TestCase):
    def test_at_returns_every_id_on_the_same_coordinate(self):
        index = PointIndex()
        index.add("a", 31.2304, 121.4737)
        index.add("b", 31.2304, 121.4737)
        index.add("c", 31.2305, 121.4737)
        self.assertEqual(index.at(31.2304, 121.4737), ["a", "b"])
        self.assertEqual(index.at(31.2305, 121.4737), ["c"])
        self.assertEqual(index.at(31.23, 121.47), [])

    def test_at_normalizes_the_lon_argument(self):
        index = PointIndex()
        index.add("a", 10.0, 180.0)
        self.assertEqual(index.at(10.0, 180.0), ["a"])
        self.assertEqual(index.at(10.0, -180.0), ["a"])
        self.assertEqual(index.at(10.0, 540.0), ["a"])

    def test_duplicate_id_rejected(self):
        index = PointIndex()
        index.add("a", 1.0, 2.0)
        with self.assertRaises(DuplicateId):
            index.add("a", 3.0, 4.0)
        self.assertEqual(len(index), 1)

    def test_bad_coordinate_leaves_index_untouched(self):
        index = PointIndex()
        for lat, lon in ((91.0, 0.0), (0.0, float("nan")), ("0", 0.0)):
            with self.assertRaises(InvalidCoordinate):
                index.add("x", lat, lon)
        self.assertEqual(len(index), 0)
        self.assertEqual(index.stats()["cells"], 0)

    def test_ids_of_any_hashable_type_work(self):
        index = PointIndex()
        index.add(7, 1.0, 1.0)
        index.add(("chain", 3), 1.0, 1.0)
        self.assertEqual(index.at(1.0, 1.0), [7, ("chain", 3)])


class RemoveAndScanTest(unittest.TestCase):
    def test_remove_returns_normalized_coordinate(self):
        index = PointIndex()
        index.add("a", 10.0, 190.0)
        self.assertEqual(index.remove("a"), (10.0, -170.0))
        self.assertEqual(index.at(10.0, -170.0), [])
        self.assertNotIn("a", index)

    def test_remove_then_add_same_id_again(self):
        index = PointIndex()
        index.add("a", 1.0, 1.0)
        index.remove("a")
        index.add("a", 2.0, 2.0)
        self.assertEqual(index.at(2.0, 2.0), ["a"])

    def test_remove_unknown_id_raises(self):
        with self.assertRaises(UnknownId):
            PointIndex().remove("ghost")

    def test_scan_keeps_registration_order(self):
        index = PointIndex()
        points = [("a", 1.0, 1.0), ("b", 2.0, 2.0), ("c", 3.0, 3.0)]
        for pid, lat, lon in points:
            index.add(pid, lat, lon)
        self.assertEqual(index.scan(), points)
        index.remove("b")
        self.assertEqual(index.scan(), [("a", 1.0, 1.0), ("c", 3.0, 3.0)])

    def test_scan_of_empty_index(self):
        self.assertEqual(PointIndex().scan(), [])


class CellOrganizationTest(unittest.TestCase):
    def test_default_cell_deg_buckets_nearby_points_together(self):
        index = PointIndex()
        index.add("a", 0.0, 0.0)
        index.add("b", 0.001, 0.001)
        index.add("c", 0.2, 0.2)
        snap = index.stats()
        self.assertEqual(snap["points"], 3)
        self.assertEqual(snap["cells"], 2)
        self.assertEqual(snap["max_cell"], 2)

    def test_custom_cell_deg_changes_bucketing(self):
        coarse = PointIndex(cell_deg=1.0)
        coarse.add("a", 0.5, 0.5)
        coarse.add("b", 0.9, 0.9)
        self.assertEqual(coarse.stats()["cells"], 1)
        fine = PointIndex(cell_deg=0.05)
        fine.add("a", 0.5, 0.5)
        fine.add("b", 0.9, 0.9)
        self.assertEqual(fine.stats()["cells"], 2)

    def test_bad_cell_deg_rejected_at_construction(self):
        for bad in (0.0, -1.0, 7.0, "1"):
            with self.assertRaises(ValueError):
                PointIndex(cell_deg=bad)

    def test_removing_last_point_releases_the_cell(self):
        index = PointIndex()
        index.add("a", 5.0, 5.0)
        index.remove("a")
        self.assertEqual(index.stats()["cells"], 0)
        self.assertEqual(index.stats()["max_cell"], 0)


class StatsTest(unittest.TestCase):
    def test_lookups_and_hits_counted(self):
        index = PointIndex()
        index.add("a", 0.0, 0.0)
        index.at(0.0, 0.0)
        index.at(0.0, 0.0)
        index.at(5.0, 5.0)
        snap = index.stats()
        self.assertEqual(snap["lookups"], 3)
        self.assertEqual(snap["hits"], 2)
        self.assertEqual(snap["points"], 1)


if __name__ == "__main__":
    unittest.main()
