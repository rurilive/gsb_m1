"""EventCounter 现有行为的锁定测试。"""

import unittest

from winagg.window import EventCounter


class FakeClock:
    """可手动改读数的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now


class TestEventCounter(unittest.TestCase):
    def test_add_returns_running_total(self):
        c = EventCounter()
        self.assertEqual(c.add(10.0, 2), 2)
        self.assertEqual(c.add(11.0, 3), 5)

    def test_default_increment_is_one(self):
        c = EventCounter()
        c.add(10.0)
        self.assertEqual(c.total(), 1)

    def test_total_starts_at_zero(self):
        c = EventCounter()
        self.assertEqual(c.total(), 0)
        self.assertEqual(c.count(), 0)

    def test_total_sums_out_of_order_events(self):
        c = EventCounter()
        c.add(103.0, 5)
        c.add(100.0, 2)
        c.add(101.0, 1)
        self.assertEqual(c.total(), 8)
        self.assertEqual(c.count(), 3)

    def test_empty_span_is_none(self):
        self.assertIsNone(EventCounter().span())

    def test_span_covers_min_and_max_event_time(self):
        c = EventCounter()
        c.add(103.0, 1)
        c.add(100.0, 1)
        c.add(101.0, 1)
        self.assertEqual(c.span(), (100.0, 103.0))

    def test_span_of_single_event(self):
        c = EventCounter()
        c.add(5.0, 1)
        self.assertEqual(c.span(), (5.0, 5.0))

    def test_events_are_kept_until_reset(self):
        c = EventCounter()
        c.add(1.0, 3)
        c.add(2.0, 4)
        self.assertEqual(c.count(), 2)
        self.assertEqual(c.total(), 7)

    def test_reset_clears_everything(self):
        c = EventCounter()
        c.add(1.0, 3)
        c.reset()
        self.assertEqual(c.total(), 0)
        self.assertEqual(c.count(), 0)
        self.assertIsNone(c.span())
        self.assertIsNone(c.last_arrival())

    def test_last_arrival_none_before_any_event(self):
        self.assertIsNone(EventCounter().last_arrival())

    def test_last_arrival_uses_injected_clock(self):
        clock = FakeClock(500.0)
        c = EventCounter(clock=clock)
        c.add(10.0, 1)
        self.assertEqual(c.last_arrival(), 500.0)
        clock.now = 560.0
        c.add(12.0, 1)
        self.assertEqual(c.last_arrival(), 560.0)

    def test_last_arrival_follows_event_arrival_not_event_time(self):
        clock = FakeClock(900.0)
        c = EventCounter(clock=clock)
        c.add(800.0, 1)      # 事件时间早于时钟读数
        self.assertEqual(c.last_arrival(), 900.0)

    def test_negative_increment_is_allowed(self):
        c = EventCounter()
        c.add(1.0, 5)
        c.add(2.0, -2)
        self.assertEqual(c.total(), 3)


if __name__ == "__main__":
    unittest.main()
