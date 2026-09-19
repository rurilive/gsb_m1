"""滑动窗口 Histogram 的行为测试。"""

import threading
import time
import unittest

from metricbox.histogram import Histogram


class FakeClock:
    """可推进的线程安全时钟。"""

    def __init__(self, start=0.0):
        self._lock = threading.Lock()
        self._now = float(start)

    def __call__(self):
        with self._lock:
            return self._now

    def advance(self, seconds):
        with self._lock:
            self._now += seconds


class TestWindowSemantics(unittest.TestCase):
    def test_sample_exactly_at_boundary_is_inside(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        self.assertEqual(h.observe(1), 0)
        clock.advance(10)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5), {0.5: 1})
        self.assertEqual(h.compact(), 0)
        clock.advance(0.001)
        self.assertEqual(h.count(), 0)
        self.assertEqual(h.compact(), 1)
        with self.assertRaises(ValueError):
            h.percentiles(0.5)

    def test_observe_returns_evicted_count(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        h.observe(1)
        clock.advance(2)
        h.observe(2)
        clock.advance(4)
        self.assertEqual(h.observe(3), 1)
        self.assertEqual(h.count(), 2)

    def test_percentiles_only_count_window_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        h.observe(1)
        h.observe(2)
        clock.advance(6)
        h.observe(100)
        clock.advance(5)
        self.assertEqual(h.percentiles(0.0, 1.0)[1.0], 100)

    def test_compact_removes_expired_samples(self):
        clock = FakeClock()
        h = Histogram(window_seconds=5, clock=clock)
        for v in (1, 2, 3):
            h.observe(v)
        clock.advance(6)
        self.assertEqual(h.count(), 0)
        self.assertEqual(h.compact(), 3)
        self.assertEqual(h.compact(), 0)

    def test_snapshot_buckets(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        for v in (-1, 0, 5, 10, 10, 11, 99):
            h.observe(v)
        self.assertEqual(h.snapshot([0, 10]), [1, 2, 4])
        clock.advance(11)
        self.assertEqual(h.snapshot([0, 10]), [0, 0, 0])

    def test_snapshot_requires_strictly_increasing_edges(self):
        h = Histogram()
        with self.assertRaises(ValueError):
            h.snapshot([1, 1])
        with self.assertRaises(ValueError):
            h.snapshot([2, 1])

    def test_disabled_window_keeps_original_behavior(self):
        h = Histogram()
        self.assertEqual(h.observe(1), 0)
        h.observe(2)
        self.assertEqual(h.snapshot([1, 2]), [0, 1, 1])
        self.assertEqual(h.compact(), 0)

    def test_negative_window_rejected(self):
        with self.assertRaises(ValueError):
            Histogram(window_seconds=-1)

    def test_default_clock_is_monotonic(self):
        h = Histogram(window_seconds=60)
        h.observe(1)
        self.assertEqual(h.count(), 1)
        self.assertEqual(h.percentiles(0.5)[0.5], 1)
        time.sleep(0.01)
        self.assertEqual(h.compact(), 0)


class TestWindowThreadSafety(unittest.TestCase):
    def test_concurrent_observes_eviction_accounting(self):
        clock = FakeClock()
        h = Histogram(window_seconds=10, clock=clock)
        start = threading.Event()

        def batch(begin):
            start.wait()
            for v in range(begin, begin + 250):
                h.observe(v)

        threads = [threading.Thread(target=batch, args=(1 + 250 * i,))
                   for i in range(4)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()
        self.assertEqual(h.count(), 1000)

        evicted_total = []
        clock.advance(11)
        start = threading.Event()

        def observe_and_report():
            start.wait()
            evicted_total.append(h.observe(0))

        reporters = [threading.Thread(target=observe_and_report)
                     for _ in range(4)]
        for t in reporters:
            t.start()
        start.set()
        for t in reporters:
            t.join()
        self.assertEqual(sum(evicted_total), 1000)
        self.assertEqual(h.count(), 4)
        self.assertEqual(h.compact(), 0)
        counts = h.snapshot([0])
        self.assertEqual(sum(counts), 4)


if __name__ == "__main__":
    unittest.main()
