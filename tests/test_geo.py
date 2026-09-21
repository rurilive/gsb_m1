"""坐标工具与球面距离的既有行为锁定。"""

import unittest

from geogrid.errors import InvalidCoordinate
from geogrid.geo import EARTH_RADIUS_M, haversine_m, normalize_lon
from geogrid.geo import check_lat, check_lon


class NormalizeLonTest(unittest.TestCase):
    def test_in_range_lon_unchanged(self):
        for lon in (0.0, 121.4737, -179.9, 179.9):
            self.assertAlmostEqual(normalize_lon(lon), lon, places=12)

    def test_lon_beyond_half_circle_wraps(self):
        self.assertAlmostEqual(normalize_lon(190.0), -170.0, places=9)
        self.assertAlmostEqual(normalize_lon(-190.0), 170.0, places=9)
        self.assertAlmostEqual(normalize_lon(390.0), 30.0, places=9)

    def test_180_folds_onto_minus_180(self):
        self.assertEqual(normalize_lon(180.0), -180.0)
        self.assertEqual(normalize_lon(-180.0), -180.0)


class CheckCoordinateTest(unittest.TestCase):
    def test_lat_bounds_are_inclusive(self):
        self.assertEqual(check_lat(-90.0), -90.0)
        self.assertEqual(check_lat(90.0), 90.0)
        for bad in (90.0001, -90.0001, "31.2", True, float("nan")):
            with self.assertRaises(InvalidCoordinate):
                check_lat(bad)

    def test_lon_accepts_any_finite_number(self):
        self.assertEqual(check_lon(540.0), 540.0)
        for bad in (float("nan"), float("inf"), None):
            with self.assertRaises(InvalidCoordinate):
                check_lon(bad)


class HaversineTest(unittest.TestCase):
    def test_same_point_is_zero(self):
        self.assertEqual(haversine_m(31.2304, 121.4737, 31.2304, 121.4737), 0.0)

    def test_one_degree_of_latitude(self):
        self.assertAlmostEqual(haversine_m(0.0, 0.0, 1.0, 0.0), 111195.08, delta=1.0)

    def test_across_antimeridian_takes_the_short_way(self):
        self.assertAlmostEqual(haversine_m(0.0, 179.9, 0.0, -179.9), 22239.02, delta=1.0)

    def test_pole_longitude_does_not_matter(self):
        self.assertAlmostEqual(haversine_m(90.0, 0.0, 90.0, 10.0), 0.0, delta=1e-6)

    def test_radius_constant_is_used(self):
        self.assertAlmostEqual(haversine_m(0.0, 0.0, 0.0, 1.0), EARTH_RADIUS_M * 0.017453292519943295, delta=0.5)


if __name__ == "__main__":
    unittest.main()
