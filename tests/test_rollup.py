"""RollupStore 行为：对齐窗口、迟到点合并、归档幂等、按范围选层。"""
import unittest

from tsdb import RollupStore


class TestRollupStore(unittest.TestCase):
    def test_windows_align_to_epoch_not_first_point(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(59, 1.0), (60, 2.0), (119, 3.0)])
        s.archive(1000)
        self.assertEqual(s.query(0, 1000), [(0, 1.0), (60, 2.5)])

    def test_archive_is_idempotent(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(10, 1.0), (20, 3.0), (70, 10.0)])
        s.archive(600)
        first = s.query(0, 1000)
        s.archive(600)
        s.archive(600)
        self.assertEqual(s.query(0, 1000), first)
        self.assertEqual(first, [(0, 2.0), (60, 10.0)])

    def test_late_points_merge_into_archived_window(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(10, 1.0), (20, 3.0)])
        s.archive(600)
        s.write(30, 5.0)
        self.assertEqual(s.query(0, 600), [(0, 3.0)])
        self.assertEqual(len(s), 0)

    def test_archive_drops_raw_points(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(10, 1.0), (20, 2.0), (700, 3.0)])
        s.archive(600)
        self.assertEqual(len(s), 1)

    def test_small_range_queries_raw_points(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(10, 1.0), (20, 2.0)])
        self.assertEqual(s.query(10, 20), [(10, 1.0), (20, 2.0)])

    def test_large_range_uses_coarsest_layer_with_enough_buckets(self):
        s = RollupStore(resolutions=(60, 3600))
        s.write_many([(100, 1.0), (3700, 3.0)])
        s.archive(7200)
        self.assertEqual(s.query(0, 7200), [(0, 1.0), (3600, 3.0)])

    def test_query_combines_archived_buckets_with_recent_raw_tail(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(10, 2.0), (20, 4.0), (5000, 10.0)])
        s.archive(600)
        self.assertEqual(s.query(0, 5000), [(0, 3.0), (5000, 10.0)])

    def test_partial_windows_at_range_edges_are_excluded(self):
        s = RollupStore(resolutions=(60,))
        s.write_many([(10, 2.0), (70, 4.0)])
        s.archive(1000)
        self.assertEqual(s.query(30, 1000), [(60, 4.0)])


if __name__ == "__main__":
    unittest.main()
