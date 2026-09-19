"""滑动窗口行为的测试。"""

import threading
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可手动推进的注入时钟。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestWindowSemantics(unittest.TestCase):
    def test_no_window_keeps_everything(self):
        clock = FakeClock()
        h = Histogram(clock=clock)
        for v in (1, 2, 3):
            self.assertEqual(h.observe(v), 0)
        clock.advance(10_000)
        self.assertEqual(h.count(), 3)
        self.assertEqual(h.compact(), 0)

    def test_expired_samples_leave_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(100)
        clock.advance(5)
        h.observe(200)
        self.assertEqual(h.count(), 2)
        clock.advance(6)  # t=0 的样本 11 秒前，出窗
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 200})

    def test_exactly_window_seconds_old_stays_inside(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(42)
        clock.advance(10)  # 恰满 window_seconds，算窗口内
        self.assertEqual(h.count(), 1)
        clock.advance(0.001)
        self.assertEqual(h.count(), 0)

    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(5)
        self.assertEqual(h.observe(3), 0)
        clock.advance(6)  # t=0 的两个样本过期，t=5 的仍在窗口内
        self.assertEqual(h.observe(4), 2)
        self.assertEqual(h.observe(5), 0)
        self.assertEqual(h.count(), 3)

    def test_compact_purges_and_reports(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(5)
        h.observe(3)
        clock.advance(6)
        self.assertEqual(h.compact(), 2)
        self.assertEqual(h.compact(), 0)  # 已清理，无新增
        self.assertEqual(h.count(), 1)

    def test_percentiles_reflect_only_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (1000, 2000, 3000):  # 旧高延迟样本
            h.observe(v)
        clock.advance(11)
        for v in (10, 20, 30):
            h.observe(v)
        self.assertEqual(h.percentiles(0.5, 1.0), {0.5: 20, 1.0: 30})

    def test_empty_window_raises(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        clock.advance(11)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)


class TestSnapshot(unittest.TestCase):
    def test_buckets_with_edge_values_going_right(self):
        clock = FakeClock()
        h = Histogram(window_seconds=60, clock=clock)
        for v in (5, 10, 10, 20, 25, 100):
            h.observe(v)
        # 边界 10、20：等于边界的值归右桶
        self.assertEqual(h.snapshot([10, 20]), [1, 2, 3])

    def test_snapshot_only_counts_window(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        clock.advance(11)
        h.observe(2)
        h.observe(50)
        self.assertEqual(h.snapshot([10]), [1, 1])

    def test_snapshot_rejects_non_increasing_edges(self):
        h = Histogram(window_seconds=10, clock=FakeClock())
        with self.assertRaises(ValueError):
            h.snapshot([10, 10])
        with self.assertRaises(ValueError):
            h.snapshot([20, 10])

    def test_snapshot_empty_edges_single_bucket(self):
        h = Histogram(window_seconds=10, clock=FakeClock())
        h.observe(1)
        h.observe(2)
        self.assertEqual(h.snapshot([]), [2])


class TestWindowThreadSafety(unittest.TestCase):
    def test_concurrent_observe_and_eviction(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(999)  # t=0 的老样本
        start = threading.Event()
        evictions = []
        evictions_lock = threading.Lock()
        threads = [
            threading.Thread(target=self._observe_batch, args=(h, start, evictions, evictions_lock))
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        clock.advance(10)  # 老样本恰满窗口，仍在窗口内
        start.set()
        for t in threads:
            t.join()
        self.assertEqual(sum(evictions), 0)
        self.assertEqual(h.count(), 1001)

        clock.advance(0.5)  # 老样本过期，新样本仍在窗口内
        self.assertEqual(h.observe(1), 1)
        self.assertEqual(h.count(), 1001)

    @staticmethod
    def _observe_batch(h, start, evictions, lock):
        start.wait()
        for v in range(1, 251):
            evicted = h.observe(v)
            if evicted:
                with lock:
                    evictions.append(evicted)


if __name__ == "__main__":
    unittest.main()
