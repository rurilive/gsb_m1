"""三态熔断器 half-open 行为测试：探测名额、闭合/重开、冷却抖动。"""

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


class ScriptedRandom:
    """按预设序列返回 r 值的伪随机源。"""

    def __init__(self, values):
        self._values = list(values)
        self._index = 0

    def __call__(self):
        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value


def make_half_open(clock, cooldown=30.0, random_values=(0.0,)):
    """首次熔断并把冷却走完，落到 half-open。"""
    b = CircuitBreaker(
        threshold=1,
        cooldown=cooldown,
        clock=clock,
        random=ScriptedRandom(random_values),
    )
    b.record_failure()
    clock.advance(cooldown)
    assert b.state == CircuitBreaker.HALF_OPEN
    return b


class TestHalfOpenEntry(unittest.TestCase):
    def test_cooldown_end_enters_half_open(self):
        clock = FakeClock()
        b = make_half_open(clock)
        self.assertFalse(b.is_open())
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)

    def test_within_cooldown_still_open(self):
        clock = FakeClock()
        b = make_half_open(clock, cooldown=30.0)
        # make_half_open 已消费首次冷却；这里另开一个验证冷却中段拒绝
        clock2 = FakeClock()
        b2 = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock2)
        b2.record_failure()
        clock2.advance(29.999)
        self.assertTrue(b2.is_open())
        self.assertFalse(b2.allow_request())


class TestProbeQuota(unittest.TestCase):
    def test_concurrent_allow_request_never_overshoots(self):
        clock = FakeClock()
        b = make_half_open(clock)
        allowed = []
        start = threading.Event()

        def worker():
            start.wait()
            if b.allow_request():
                allowed.append(threading.get_ident())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()

        self.assertEqual(len(allowed), 3)
        self.assertEqual(len(set(allowed)), 3)
        self.assertFalse(b.allow_request())

    def test_finished_probe_frees_slot_but_capped_at_three(self):
        clock = FakeClock()
        b = make_half_open(clock)
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())
        b.record_success()
        self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())


class TestCloseOnSuccess(unittest.TestCase):
    def test_two_successes_close_and_reset_counts(self):
        clock = FakeClock()
        b = make_half_open(clock)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertEqual(b.state, CircuitBreaker.CLOSED)
        self.assertTrue(b.allow_request())
        # 闭合并清零失败计数：threshold=3 时单次失败不得立即重开
        b2_clock = FakeClock()
        b2 = CircuitBreaker(threshold=3, cooldown=30.0, clock=b2_clock)
        for _ in range(3):
            b2.record_failure()
        self.assertTrue(b2.is_open())
        b2_clock.advance(30.0)
        self.assertEqual(b2.state, CircuitBreaker.HALF_OPEN)
        b2.allow_request()
        b2.record_success()
        b2.allow_request()
        b2.record_success()
        self.assertEqual(b2.state, CircuitBreaker.CLOSED)
        b2.record_failure()
        self.assertFalse(b2.is_open())
        self.assertTrue(b2.allow_request())


class TestReopenOnFailure(unittest.TestCase):
    def test_any_failure_reopens_and_restarts_jittered_cooldown(self):
        clock = FakeClock()
        b = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock,
            random=ScriptedRandom([0.0]),
        )
        b.record_failure()
        clock.advance(30.0)
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertTrue(b.allow_request())
        b.record_failure()  # 重开抽抖动：r=0 -> 24s

        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())
        clock.advance(23.999)
        self.assertTrue(b.is_open())
        clock.advance(0.01)
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)

    def test_issued_slots_voided_after_reopen(self):
        clock = FakeClock()
        b = make_half_open(clock, random_values=(0.0,))
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        b.record_failure()  # 已发探测名额全部作废
        self.assertTrue(b.is_open())
        b.record_success()  # 熔断中漏报不改变状态
        self.assertTrue(b.is_open())
        clock.advance(24.0)
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)
        # 名额重置为全新一轮
        for _ in range(3):
            self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())


class TestCooldownJitter(unittest.TestCase):
    def test_first_trip_uses_base_cooldown_regardless_of_r(self):
        clock = FakeClock()
        b = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock,
            random=ScriptedRandom([1.0 - 2 ** -53]),
        )
        b.record_failure()
        clock.advance(29.999)
        self.assertTrue(b.is_open())
        clock.advance(0.001)
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)

    def test_lower_boundary_on_reopen(self):
        clock = FakeClock()
        b = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock,
            random=ScriptedRandom([0.0]),
        )
        b.record_failure()
        clock.advance(30.0)
        b.record_failure()  # r=0 -> 0.8 * 30 = 24s
        self.assertTrue(b.is_open())
        clock.advance(23.5)
        self.assertTrue(b.is_open())
        clock.advance(0.5)
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)

    def test_upper_boundary_on_reopen(self):
        near_one = 1.0 - 2 ** -53

        def trip_and_check(r):
            clock = FakeClock()
            b = CircuitBreaker(
                threshold=1, cooldown=30.0, clock=clock,
                random=ScriptedRandom([r]),
            )
            b.record_failure()
            clock.advance(30.0)
            b.record_failure()
            expected = 30.0 * (0.8 + 0.4 * r)
            self.assertTrue(b.is_open())
            clock.advance(expected - 1e-12)
            self.assertTrue(b.is_open())
            clock.advance(2e-12)
            self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)

        trip_and_check(near_one)
        trip_and_check(0.5)

    def test_each_reopen_resamples(self):
        clock = FakeClock()
        b = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock,
            random=ScriptedRandom([0.0, 1.0 - 2 ** -53]),
        )
        b.record_failure()
        clock.advance(30.0)
        b.record_failure()  # 第一次重开 r=0 -> 24s
        clock.advance(24.0)
        self.assertEqual(b.state, CircuitBreaker.HALF_OPEN)
        b.record_failure()  # 第二次重开 r 接近 1 -> 接近 36s
        self.assertTrue(b.is_open())
        clock.advance(35.0)
        self.assertTrue(b.is_open())


if __name__ == "__main__":
    unittest.main()
