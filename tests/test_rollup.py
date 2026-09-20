"""降采样归档行为：窗口对齐、迟到点合并、重跑幂等、跨层查询。"""
import unittest

from tsdb import TimeSeriesStore


class TestRollup(unittest.TestCase):
    def test_windows_align_to_absolute_boundaries(self):
        s = TimeSeriesStore(window=60)
        # 59 属于窗口 0，60 和 119 属于窗口 60，与首点到达时间无关
        s.write_many([(59, 1.0), (60, 2.0), (119, 4.0)])
        s.archive()
        self.assertEqual(s.query_rollup(0, 200), [(0, 1, 1.0, 1.0, 1.0),
                                                  (60, 2, 6.0, 2.0, 4.0)])

    def test_archive_drops_archived_raw_points(self):
        s = TimeSeriesStore(window=60)
        s.write_many([(10, 1.0), (20, 2.0), (70, 3.0)])
        s.archive(before=60)  # 只归档窗口 [0, 60)
        self.assertEqual(len(s), 1)
        self.assertEqual(s.query(0, 100), [(70, 3.0)])
        self.assertEqual(s.query_rollup(0, 100), [(0, 2, 3.0, 1.0, 2.0)])

    def test_rerun_archive_is_idempotent(self):
        s = TimeSeriesStore(window=60)
        s.write_many([(10, 1.0), (20, 3.0)])
        s.archive()
        first = s.query_rollup(0, 100)
        s.archive()
        s.archive()
        self.assertEqual(s.query_rollup(0, 100), first)
        self.assertEqual(first[0][1], 2)          # count 不翻倍
        self.assertEqual(first[0][2] / first[0][1], 2.0)  # 平均值不翻倍

    def test_late_points_merge_into_archived_window(self):
        s = TimeSeriesStore(window=60)
        s.write_many([(10, 1.0), (20, 3.0)])
        s.archive()
        s.write(30, 4.0)  # 采集端时钟偏慢，窗口归档后才到
        s.archive()
        self.assertEqual(s.query_rollup(0, 100), [(0, 3, 8.0, 1.0, 4.0)])
        self.assertEqual(len(s), 0)

    def test_query_rollup_returns_only_overlapping_windows(self):
        s = TimeSeriesStore(window=60)
        s.write_many([(10, 1.0), (70, 2.0), (130, 3.0)])
        s.archive()
        self.assertEqual([r[0] for r in s.query_rollup(60, 119)], [60])
        self.assertEqual([r[0] for r in s.query_rollup(0, 200)], [0, 60, 120])

    def test_query_auto_uses_raw_for_narrow_range(self):
        s = TimeSeriesStore(window=60)
        s.write_many([(10, 1.0), (20, 2.0)])
        s.archive()
        s.write(500, 5.0)
        self.assertEqual(s.query_auto(490, 510), [(500, 5.0)])

    def test_query_auto_uses_rollup_for_wide_range(self):
        s = TimeSeriesStore(window=60)
        s.write_many([(10, 1.0), (20, 3.0), (70, 2.0), (80, 4.0)])
        s.archive()
        self.assertEqual(s.query_auto(0, 200), [(0, 2.0), (60, 3.0)])

    def test_rollup_empty_store(self):
        s = TimeSeriesStore(window=60)
        s.archive()
        self.assertEqual(s.query_rollup(0, 100), [])
        self.assertEqual(s.query_auto(0, 1000), [])


if __name__ == "__main__":
    unittest.main()
