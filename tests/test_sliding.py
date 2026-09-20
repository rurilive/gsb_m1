"""SlidingWindow / WindowSet 的行为测试。"""

import unittest

from winagg.sliding import SlidingWindow, WindowResult, WindowSet


class FakeClock:
    """可手动改读数的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


class TestSlidingWindowBounds(unittest.TestCase):
    def test_empty_window(self):
        w = SlidingWindow(10.0, 2.0)
        self.assertEqual(w.sum(), 0)
        self.assertEqual(w.count(), 0)
        self.assertIsNone(w.watermark())
        self.assertIsNone(w.left())
        self.assertEqual(w.closed(), [])

    def test_left_edge_is_closed(self):
        w = SlidingWindow(10.0, 2.0)
        w.add(100.0, 1)
        w.add(105.0, 2)          # 水位线 105，左缘 95
        self.assertEqual(w.watermark(), 105.0)
        self.assertEqual(w.left(), 95.0)
        self.assertTrue(w.add(95.0, 4))   # 恰好压在左缘上，算入
        self.assertEqual(w.sum(), 7)

    def test_before_left_edge_is_late(self):
        w = SlidingWindow(10.0, 2.0)
        w.add(105.0, 2)
        self.assertFalse(w.add(94.9, 8))  # 早于左缘，判迟到
        self.assertEqual(w.sum(), 2)
        self.assertEqual(w.late_count(), 1)
        self.assertEqual(w.late_total(), 8)

    def test_out_of_order_within_window_is_counted(self):
        w = SlidingWindow(10.0, 1.0)
        w.add(110.0, 1)
        self.assertTrue(w.add(105.0, 2))  # 乱序但落在窗口内
        self.assertEqual(w.sum(), 3)
        self.assertEqual(w.late_count(), 0)

    def test_window_advances_with_event_time_not_arrival_clock(self):
        clock = FakeClock(1000.0)
        w = SlidingWindow(10.0, 1.0, clock=clock)
        w.add(50.0, 1)
        clock.now = 9999.0       # 到达时钟走多远都不影响窗口
        w.add(51.0, 1)
        self.assertEqual(w.watermark(), 51.0)
        self.assertEqual(w.left(), 41.0)
        self.assertEqual(w.sum(), 2)
        self.assertEqual(w.closed(), [])

    def test_replay_is_reproducible(self):
        events = [(100.0, 2), (103.0, 5), (101.0, 1), (120.0, 4)]
        results = []
        for start in (0.0, 12345.0):  # 不同的到达时钟，同样的事件序列
            clock = FakeClock(start)
            w = SlidingWindow(10.0, 5.0, clock=clock)
            for ts, v in events:
                clock.now += 7.0
                w.add(ts, v)
            results.append((w.sum(), w.closed()))
        self.assertEqual(results[0], results[1])


class TestLatePolicy(unittest.TestCase):
    def test_drop_policy_discards_but_counts(self):
        w = SlidingWindow(10.0, 1.0, on_late="drop")
        w.add(100.0, 1)
        self.assertFalse(w.add(80.0, 5))
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.late_count(), 1)
        self.assertEqual(w.late_total(), 5)
        self.assertEqual(w.late(), [])     # drop 不留档

    def test_keep_policy_archives_late_events(self):
        w = SlidingWindow(10.0, 1.0, on_late="keep")
        w.add(100.0, 1)
        self.assertFalse(w.add(80.0, 5))
        self.assertFalse(w.add(85.0, 6))
        self.assertEqual(w.late(), [(80.0, 5), (85.0, 6)])
        self.assertEqual(w.late_count(), 2)
        self.assertEqual(w.late_total(), 11)

    def test_bad_policy_rejected(self):
        with self.assertRaises(ValueError):
            SlidingWindow(10.0, 1.0, on_late="ignore")


class TestEvictionOutput(unittest.TestCase):
    def test_evicted_bucket_becomes_closed_output(self):
        w = SlidingWindow(10.0, 5.0)
        w.add(100.0, 2)
        w.add(103.0, 3)          # 桶 [100, 105) 合计 5
        w.add(120.0, 1)          # 水位线 120，左缘 110，整桶滑出
        self.assertEqual(w.closed(), [WindowResult(100.0, 105.0, 5.0)])
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.count(), 1)     # 旧事件真的被淘汰了

    def test_straddling_bucket_is_pruned_then_emitted_in_full(self):
        w = SlidingWindow(10.0, 5.0)
        w.add(100.0, 2)          # 桶 [100, 105)
        w.add(112.0, 1)          # 左缘 102，跨缘桶先剪掉界外事件
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.count(), 1)
        w.add(120.0, 1)          # 左缘 110，桶 [100, 105) 关闭
        # 产出是该桶的完整聚合，含先被剪掉的界外部分
        self.assertEqual(w.closed(), [WindowResult(100.0, 105.0, 2.0)])

    def test_merge_adjacent_closed_results(self):
        w = SlidingWindow(5.0, 5.0)
        w.add(100.0, 1)          # 桶 [100, 105)
        w.add(106.0, 2)          # 桶 [105, 110)
        w.add(115.0, 3)          # 左缘 110，[100,105) 与 [105,110) 关闭
        w.add(120.0, 4)
        self.assertEqual(w.closed(), [WindowResult(100.0, 105.0, 1.0),
                                      WindowResult(105.0, 110.0, 2.0)])
        self.assertEqual(w.merge_closed(),
                         [WindowResult(100.0, 110.0, 3.0)])

    def test_merge_skips_non_contiguous_results(self):
        w = SlidingWindow(5.0, 5.0)
        w.add(100.0, 1)
        w.add(106.0, 2)
        w.add(115.0, 3)
        w.add(120.0, 4)
        w.add(140.0, 1)          # 左缘 135，[115,120) 与 [120,125) 关闭
        # [110,115) 没有事件，产出序列在 110 处断开，不能合并
        self.assertEqual(w.merge_closed(),
                         [WindowResult(100.0, 110.0, 3.0),
                          WindowResult(115.0, 125.0, 7.0)])

    def test_merge_only_sees_unexpired_results(self):
        w = SlidingWindow(5.0, 5.0, closed_retention=1)
        w.add(100.0, 1)          # 桶 [100, 105)
        w.add(110.0, 3)          # 左缘 105，[100,105) 关闭
        w.add(120.0, 4)          # 左缘 115，[110,115) 关闭，最老一条过期
        self.assertEqual(w.closed(), [WindowResult(110.0, 115.0, 3.0)])
        self.assertEqual(w.merge_closed(),
                         [WindowResult(110.0, 115.0, 3.0)])


class TestWindowSet(unittest.TestCase):
    def test_windows_evict_independently(self):
        ws = WindowSet()
        short = ws.add_window(10.0, 5.0)
        long_ = ws.add_window(30.0, 5.0)
        ws.add(100.0, 1)
        ws.add(125.0, 2)
        # 短窗口左缘 115，[100,105) 到点就走；长窗口左缘 95，仍保留
        self.assertEqual(short.sum(), 2)
        self.assertEqual(short.closed(), [WindowResult(100.0, 105.0, 1.0)])
        self.assertEqual(long_.sum(), 3)
        self.assertEqual(long_.closed(), [])
        self.assertEqual(ws.sums(), [2, 3])

    def test_add_returns_per_window_results(self):
        ws = WindowSet()
        ws.add_window(10.0, 5.0)
        ws.add_window(30.0, 5.0)
        ws.add(100.0, 1)
        # 对短窗口迟到、对长窗口仍在窗口内
        self.assertEqual(ws.add(85.0, 1), [False, True])


class TestMisc(unittest.TestCase):
    def test_size_must_be_multiple_of_bucket(self):
        with self.assertRaises(ValueError):
            SlidingWindow(10.0, 3.0)

    def test_default_increment_and_negative_values(self):
        w = SlidingWindow(10.0, 1.0)
        w.add(100.0)
        w.add(101.0, 5)
        w.add(102.0, -2)
        self.assertEqual(w.sum(), 4)

    def test_last_arrival_uses_injected_clock(self):
        clock = FakeClock(500.0)
        w = SlidingWindow(10.0, 1.0, clock=clock)
        w.add(10.0, 1)
        self.assertEqual(w.last_arrival(), 500.0)

    def test_reset_clears_everything(self):
        w = SlidingWindow(5.0, 5.0, on_late="keep")
        w.add(100.0, 1)
        w.add(120.0, 2)
        w.add(90.0, 1)
        w.reset()
        self.assertEqual(w.sum(), 0)
        self.assertEqual(w.count(), 0)
        self.assertIsNone(w.watermark())
        self.assertIsNone(w.left())
        self.assertEqual(w.closed(), [])
        self.assertEqual(w.late_count(), 0)
        self.assertEqual(w.late(), [])
        self.assertIsNone(w.last_arrival())


if __name__ == "__main__":
    unittest.main()
