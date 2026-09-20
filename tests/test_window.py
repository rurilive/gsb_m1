"""SlidingWindow 现有行为的锁定测试。"""

import unittest

from tracesamp import ManualClock, SlidingWindow


def make_window(window_seconds=1.0, buckets=4):
    clock = ManualClock()
    return SlidingWindow(window_seconds, buckets, clock), clock


class TestCounters(unittest.TestCase):
    def test_count_is_zero_when_empty(self):
        window, _ = make_window()
        self.assertEqual(window.count("total"), 0)
        self.assertEqual(window.per_second("total"), 0.0)

    def test_add_and_count_same_instant(self):
        window, _ = make_window()
        for _ in range(5):
            window.add("total")
        self.assertEqual(window.count("total"), 5)

    def test_add_with_step(self):
        window, _ = make_window()
        window.add("total", 7)
        window.add("total", 2)
        self.assertEqual(window.count("total"), 9)

    def test_keys_are_counted_separately(self):
        window, _ = make_window()
        window.add("total", 4)
        window.add("sampled", 1)
        self.assertEqual(window.count("total"), 4)
        self.assertEqual(window.count("sampled"), 1)
        self.assertEqual(window.count("dropped"), 0)

    def test_per_second_divides_by_window(self):
        window, _ = make_window(window_seconds=2.0)
        window.add("total", 10)
        self.assertEqual(window.per_second("total"), 5.0)

    def test_quarter_of_a_bucket_still_counts(self):
        window, clock = make_window()
        window.add("total", 3)
        clock.advance(0.2)
        window.add("total", 2)
        self.assertEqual(window.count("total"), 5)


class TestExpiry(unittest.TestCase):
    def test_counts_expire_after_long_idle(self):
        window, clock = make_window()
        window.add("total", 10)
        clock.advance(30.0)
        self.assertEqual(window.count("total"), 0)
        self.assertEqual(window.count("sampled"), 0)

    def test_stale_data_is_not_resurrected(self):
        window, clock = make_window()
        window.add("total", 100)
        clock.advance(30.0)
        window.add("total", 1)
        self.assertEqual(window.count("total"), 1)

    def test_count_never_exceeds_what_was_written(self):
        window, clock = make_window()
        for _ in range(10):
            window.add("total")
            clock.advance(0.1)
        self.assertLessEqual(window.count("total"), 10)

    def test_reset_clears_everything(self):
        window, _ = make_window()
        window.add("total", 5)
        window.reset()
        self.assertEqual(window.count("total"), 0)

    def test_window_seconds_property(self):
        window, _ = make_window(window_seconds=3.0)
        self.assertEqual(window.window_seconds, 3.0)


class TestValidation(unittest.TestCase):
    def test_window_seconds_must_be_positive(self):
        with self.assertRaises(ValueError):
            SlidingWindow(0.0, 4, ManualClock())

    def test_buckets_must_be_positive(self):
        with self.assertRaises(ValueError):
            SlidingWindow(1.0, 0, ManualClock())


if __name__ == "__main__":
    unittest.main()
