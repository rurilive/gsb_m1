"""TimeSeriesStore 行为基线：锁死现有写入与区间查询语义。"""
import unittest

from tsdb import TimeSeriesStore


class TestTimeSeriesStore(unittest.TestCase):
    def test_query_returns_points_in_time_order(self):
        s = TimeSeriesStore()
        s.write_many([(100, 1.0), (300, 3.0), (200, 2.0)])
        self.assertEqual(s.query(100, 300), [(100, 1.0), (200, 2.0), (300, 3.0)])

    def test_query_range_is_closed_on_both_ends(self):
        s = TimeSeriesStore()
        s.write_many([(10, 1.0), (20, 2.0), (30, 3.0), (40, 4.0)])
        self.assertEqual(s.query(20, 30), [(20, 2.0), (30, 3.0)])

    def test_query_excludes_points_outside_range(self):
        s = TimeSeriesStore()
        s.write_many([(10, 1.0), (20, 2.0), (30, 3.0)])
        self.assertEqual(s.query(25, 35), [(30, 3.0)])
        self.assertEqual(s.query(11, 19), [])

    def test_out_of_order_writes_are_sorted(self):
        s = TimeSeriesStore()
        s.write(500, 5.0)
        s.write(100, 1.0)
        s.write(300, 3.0)
        self.assertEqual(s.query(0, 1000), [(100, 1.0), (300, 3.0), (500, 5.0)])

    def test_duplicate_timestamps_are_both_kept(self):
        s = TimeSeriesStore()
        s.write(100, 1.0)
        s.write(100, 2.0)
        self.assertEqual(s.query(100, 100), [(100, 1.0), (100, 2.0)])

    def test_span_and_len(self):
        s = TimeSeriesStore()
        self.assertIsNone(s.span())
        self.assertEqual(len(s), 0)
        s.write_many([(70, 1.0), (30, 2.0), (90, 3.0)])
        self.assertEqual(s.span(), (30, 90))
        self.assertEqual(len(s), 3)

    def test_query_empty_store(self):
        self.assertEqual(TimeSeriesStore().query(0, 100), [])


if __name__ == "__main__":
    unittest.main()
