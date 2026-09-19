"""Histogram 现有行为的锁定测试。"""

import threading
import unittest

from metricbox.histogram import Histogram


class TestBasicAggregation(unittest.TestCase):
    def test_observe_then_count(self):
        h = Histogram()
        self.assertEqual(h.count(), 0)
        for v in (3, 1, 2):
            h.observe(v)
        self.assertEqual(h.count(), 3)

    def test_percentiles_single_sample(self):
        h = Histogram()
        h.observe(10)
        self.assertEqual(h.percentiles(0.5), {0.5: 10})

    def test_percentiles_are_interpolated(self):
        h = Histogram()
        for v in (1, 2, 3, 4):
            h.observe(v)
        self.assertEqual(h.percentiles(0.5), {0.5: 2.5})

    def test_percentiles_multiple_fractions(self):
        h = Histogram()
        for v in (10, 20, 30, 40, 50):
            h.observe(v)
        ps = h.percentiles(0.0, 0.5, 1.0)
        self.assertEqual(ps[0.0], 10)
        self.assertEqual(ps[0.5], 30)
        self.assertEqual(ps[1.0], 50)

    def test_order_does_not_matter(self):
        a = Histogram()
        b = Histogram()
        for v in (40, 10, 30, 20):
            a.observe(v)
        for v in (10, 20, 30, 40):
            b.observe(v)
        self.assertEqual(a.percentiles(0.9), b.percentiles(0.9))

    def test_empty_raises(self):
        h = Histogram()
        with self.assertRaises(ValueError):
            h.percentiles(0.5)


class TestThreadSafety(unittest.TestCase):
    def test_concurrent_observes_are_all_counted(self):
        h = Histogram()
        start = threading.Event()
        threads = [
            threading.Thread(target=self._observe_batch, args=(h, start))
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()
        self.assertEqual(h.count(), 1000)
        # 1..250 各出现 4 次，中位数插值落点固定
        self.assertEqual(h.percentiles(0.5)[0.5], 125.5)

    @staticmethod
    def _observe_batch(h, start):
        start.wait()
        for v in range(1, 251):
            h.observe(v)


if __name__ == "__main__":
    unittest.main()
