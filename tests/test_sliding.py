"""SlidingWindow / MultiWindow 的行为测试。"""

import unittest

from winagg.sliding import ClosedWindow, MultiWindow, SlidingWindow


class FakeClock:
    """可手动改读数的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


class TestSlidingWindow(unittest.TestCase):
    def test_left_boundary_is_closed(self):
        w = SlidingWindow(10, clock=FakeClock())
        w.add(100.0, 1)      # watermark 100，左边界 90
        w.add(90.0, 2)       # 恰好左边界，闭，计入
        w.add(89.0, 4)       # 出界，默认 drop
        self.assertEqual(w.sum(), 3)
        self.assertEqual(w.dropped(), 1)

    def test_window_advances_by_event_time_not_arrival(self):
        clock = FakeClock(5000.0)
        w = SlidingWindow(10, clock=clock)
        w.add(100.0, 1)
        clock.now = 9999.0   # 到达时钟远远超前，不影响窗口
        w.add(101.0, 2)
        self.assertEqual(w.watermark(), 101.0)
        self.assertEqual(w.sum(), 3)
        self.assertEqual(w.last_arrival(), 9999.0)

    def test_eviction_is_real_not_query_time(self):
        w = SlidingWindow(10)
        for i in range(10):
            w.add(float(i), 1)
        self.assertEqual(w.buffered(), 10)
        w.add(15.0, 1)       # 左边界推到 5，ts<5 真被淘汰
        self.assertEqual(w.buffered(), 6)
        self.assertEqual(w.sum(), 6)

    def test_late_event_within_window_is_counted(self):
        w = SlidingWindow(10)
        w.add(100.0, 1)
        w.add(105.0, 2)      # 左边界 95
        w.add(98.0, 4)       # 迟到但落在窗口内
        self.assertEqual(w.sum(), 7)
        self.assertEqual(w.dropped(), 0)

    def test_late_beyond_boundary_drop_policy(self):
        w = SlidingWindow(10, late_policy="drop")
        w.add(100.0, 1)
        w.add(89.0, 4)
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.dropped(), 1)
        self.assertEqual(w.late(), (0, 0.0))

    def test_late_beyond_boundary_count_policy(self):
        w = SlidingWindow(10, late_policy="count")
        w.add(100.0, 1)
        w.add(89.0, 4)
        self.assertEqual(w.sum(), 1)
        self.assertEqual(w.late(), (1, 4.0))
        self.assertEqual(w.dropped(), 0)

    def test_tumbling_boundary_is_closed_open(self):
        w = SlidingWindow(10)
        w.add(10.0, 7)       # 恰好落在 [10, 20)，不归 [0, 10)
        w.add(20.0, 1)       # 触发 [10, 20) 关闭
        (em,) = w.emissions()
        self.assertEqual((em.start, em.end, em.total, em.count),
                         (10.0, 20.0, 7.0, 1))

    def test_closed_window_is_emitted_and_drained(self):
        w = SlidingWindow(10)
        w.add(1.0, 2)
        w.add(5.0, 3)
        self.assertEqual(w.emissions(), ())
        w.add(10.0, 1)       # watermark 10，[0, 10) 关闭
        (em,) = w.emissions()
        self.assertEqual((em.start, em.end, em.total, em.count),
                         (0.0, 10.0, 5.0, 2))
        self.assertEqual(w.drain_emissions(), [em])
        self.assertEqual(w.emissions(), ())

    def test_late_event_does_not_change_closed_emission(self):
        w = SlidingWindow(10)
        w.add(1.0, 2)
        w.add(10.0, 1)       # [0, 10) 已关闭产出 total=2
        w.add(5.0, 8)        # 同段迟到：进滑动窗，不改已产出
        self.assertEqual(w.sum(), 11)
        (em,) = w.emissions()
        self.assertEqual(em.total, 2.0)

    def test_merge_adjacent_closed_windows(self):
        w = SlidingWindow(10)
        w.add(1.0, 2)
        w.add(12.0, 3)       # 产出 [0, 10)
        w.add(25.0, 5)       # 产出 [10, 20)
        a, b = w.emissions()
        merged = w.merge(a, b)
        self.assertEqual((merged.start, merged.end, merged.total, merged.count),
                         (0.0, 20.0, 5.0, 2))

    def test_merge_rejects_non_adjacent(self):
        w = SlidingWindow(10)
        a = ClosedWindow(0.0, 10.0, 1.0, 1)
        b = ClosedWindow(20.0, 30.0, 1.0, 1)
        with self.assertRaises(ValueError):
            w.merge(a, b)
        with self.assertRaises(ValueError):
            w.merge(b, a)

    def test_merge_rejects_expired_and_emissions_purged(self):
        w = SlidingWindow(10, emission_retention=10)
        w.add(1.0, 2)
        w.add(12.0, 3)       # 产出 a=[0, 10)
        (a,) = w.emissions()
        w.add(25.0, 1)       # watermark 25，a 过期被清除
        self.assertNotIn(a, w.emissions())
        b = ClosedWindow(10.0, 20.0, 1.0, 1)
        with self.assertRaises(ValueError):
            w.merge(a, b)


class TestMultiWindow(unittest.TestCase):
    def test_windows_evict_independently(self):
        mw = MultiWindow([5, 10], clock=FakeClock())
        mw.add(0.0, 1)
        mw.add(4.0, 2)
        mw.add(9.0, 4)       # 短窗左边界 4，长窗左边界 -1
        self.assertEqual(mw.sum(5), 6)
        self.assertEqual(mw.sum(10), 7)
        self.assertEqual(mw.window(5).buffered(), 2)
        self.assertEqual(mw.window(10).buffered(), 3)

    def test_short_window_emits_earlier(self):
        mw = MultiWindow([5, 10])
        mw.add(1.0, 1)
        mw.add(6.0, 1)       # 短窗 [0, 5) 关闭，长窗 [0, 10) 未关
        self.assertEqual(len(mw.window(5).emissions()), 1)
        self.assertEqual(len(mw.window(10).emissions()), 0)

    def test_sizes_round_trip(self):
        mw = MultiWindow([5, 10])
        self.assertEqual(mw.sizes(), (5.0, 10.0))


if __name__ == "__main__":
    unittest.main()
