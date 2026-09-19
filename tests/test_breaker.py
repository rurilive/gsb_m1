"""CircuitBreaker 现有两态行为的锁定测试。"""

import threading
import unittest

from breaker.core import CircuitBreaker


class FakeClock:
    """手动推进的时钟，保证测试确定。"""

    def __init__(self, start=0.0):
        self._now = start
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self._now

    def advance(self, seconds):
        with self._lock:
            self._now += seconds


class TestClosedState(unittest.TestCase):
    def test_initially_allows(self):
        b = CircuitBreaker(threshold=3, cooldown=30.0, clock=FakeClock())
        self.assertTrue(b.allow_request())
        self.assertFalse(b.is_open())

    def test_failures_below_threshold_keep_closed(self):
        b = CircuitBreaker(threshold=3, cooldown=30.0, clock=FakeClock())
        b.record_failure()
        b.record_failure()
        self.assertFalse(b.is_open())
        self.assertTrue(b.allow_request())

    def test_success_resets_consecutive_count(self):
        b = CircuitBreaker(threshold=3, cooldown=30.0, clock=FakeClock())
        b.record_failure()
        b.record_failure()
        b.record_success()
        b.record_failure()
        self.assertFalse(b.is_open())

    def test_trips_at_threshold(self):
        b = CircuitBreaker(threshold=3, cooldown=30.0, clock=FakeClock())
        for _ in range(3):
            b.record_failure()
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())


class TestOpenState(unittest.TestCase):
    def test_stays_open_after_more_failures(self):
        b = CircuitBreaker(threshold=2, cooldown=30.0, clock=FakeClock())
        b.record_failure()
        b.record_failure()
        b.record_failure()
        b.record_failure()
        self.assertTrue(b.is_open())

    def test_success_while_open_does_not_close(self):
        # 熔断期间漏进来的零星成功不改变状态
        b = CircuitBreaker(threshold=2, cooldown=30.0, clock=FakeClock())
        b.record_failure()
        b.record_failure()
        b.record_success()
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())

    def test_blocks_within_cooldown(self):
        # 冷却时间过半仍必须拒绝
        clock = FakeClock()
        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock)
        b.record_failure()
        clock.advance(15.0)
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())

    def test_allows_long_after_cooldown(self):
        clock = FakeClock()
        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock)
        b.record_failure()
        clock.advance(300.0)
        self.assertTrue(b.allow_request())


class TestClockInjection(unittest.TestCase):
    def test_breakers_use_their_own_clock(self):
        c1, c2 = FakeClock(), FakeClock(start=1000.0)
        b1 = CircuitBreaker(threshold=1, cooldown=30.0, clock=c1)
        b2 = CircuitBreaker(threshold=1, cooldown=30.0, clock=c2)
        b1.record_failure()
        b2.record_failure()
        c1.advance(30.0)
        self.assertTrue(b1.allow_request())
        self.assertFalse(b2.allow_request())


if __name__ == "__main__":
    unittest.main()
