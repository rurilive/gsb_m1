"""三态熔断器 half-open 行为测试。

全程注入假时钟与假随机源，不做真实 sleep；并发探测用
``threading.Event`` 统一发令、回收，精确定节奏。
"""

import threading
import unittest

from breaker.core import CircuitBreaker


class FakeClock:
    """手动推进的线程安全时钟。"""

    def __init__(self, start=0.0):
        self._now = start
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self._now

    def advance(self, seconds):
        with self._lock:
            self._now += seconds


class SequenceRng:
    """按序返回预设值的假随机源，耗尽即报错。"""

    def __init__(self, values):
        self._values = list(values)

    def __call__(self):
        return self._values.pop(0)


def open_breaker(clock, rng=lambda: 0.5, threshold=2, cooldown=30.0):
    """构造熔断器并打断开，时钟停在 0。"""
    b = CircuitBreaker(threshold=threshold, cooldown=cooldown,
                       clock=clock, rng=rng)
    for _ in range(threshold):
        b.record_failure()
    return b


def warm_to_half_open(b, clock, cooldown=30.0, r=0.5):
    """把 open 的熔断器推进到冷却期满，触发进入 half-open。"""
    clock.advance(cooldown * (0.8 + 0.4 * r))
    assert b.is_half_open()
    return b


class TestHalfOpenTransition(unittest.TestCase):
    def test_cooldown_boundary_is_half_open_not_closed(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.5]))
        clock.advance(30.0 * 0.8)
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())
        clock.advance(30.0 - 30.0 * 0.8)
        self.assertTrue(b.is_half_open())

    def test_not_half_open_a_hair_before_cooldown(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.5]))
        clock.advance(30.0 - 0.001)
        self.assertTrue(b.is_open())
        self.assertFalse(b.is_half_open())


class TestProbePermits(unittest.TestCase):
    def test_exactly_three_probes_pass_serially(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.5]))
        warm_to_half_open(b, clock)
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())
        self.assertTrue(b.is_half_open())

    def test_concurrent_probes_never_exceed_three(self):
        # 30 轮，每轮 8 个线程在同一 Event 上发令、同时抢名额
        rounds = 30
        for _ in range(rounds):
            clock = FakeClock()
            rng = SequenceRng([0.5])
            b = open_breaker(clock, rng=rng)
            warm_to_half_open(b, clock)

            start = threading.Event()
            results = []
            results_lock = threading.Lock()

            def probe():
                start.wait()
                allowed = b.allow_request()
                with results_lock:
                    results.append(allowed)

            threads = [threading.Thread(target=probe) for _ in range(8)]
            for t in threads:
                t.start()
            start.set()
            for t in threads:
                t.join()

            self.assertEqual(sorted(results), [False] * 5 + [True] * 3)
            self.assertTrue(b.is_half_open())


class TestHalfOpenSuccess(unittest.TestCase):
    def test_two_successes_close_and_reset_counts(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.5]))
        warm_to_half_open(b, clock)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertTrue(b.is_half_open())
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertEqual(b.state(), CircuitBreaker.CLOSED)
        self.assertTrue(b.allow_request())

        # 闭合后计数清零：阈值内的新失败不会再次断开
        b.record_failure()
        self.assertFalse(b.is_open())

    def test_single_success_does_not_close(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.5]))
        warm_to_half_open(b, clock)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertTrue(b.is_half_open())


class TestHalfOpenFailure(unittest.TestCase):
    def test_any_probe_failure_reopens_and_invalidates_permits(self):
        clock = FakeClock()
        rng = SequenceRng([0.5, 0.0, 0.5])
        b = open_breaker(clock, rng=rng)
        warm_to_half_open(b, clock)

        # 占用第一个探测名额，其失败立即重开；同批已发名额作废
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        b.record_failure()
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())

        # 重新计时：本轮抖动取 r=0，冷却 = 0.8 * cooldown
        clock.advance(24.0 - 0.001)
        self.assertTrue(b.is_open())
        clock.advance(0.002)
        self.assertTrue(b.is_half_open())

        # 名额重新发满 3 个，此前作废的名额不带入
        allowed = [b.allow_request() for _ in range(4)]
        self.assertEqual(allowed, [True, True, True, False])

    def test_failure_after_one_success_restarts_probe_counters(self):
        clock = FakeClock()
        rng = SequenceRng([0.5, 0.5])
        b = open_breaker(clock, rng=rng)
        warm_to_half_open(b, clock)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertTrue(b.allow_request())
        b.record_failure()
        self.assertTrue(b.is_open())

        # 回到 half-open 后成功计数清零，仍需两次成功才闭合
        warm_to_half_open(b, clock)
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertTrue(b.is_half_open())
        self.assertTrue(b.allow_request())
        b.record_success()
        self.assertEqual(b.state(), CircuitBreaker.CLOSED)


class TestJitterBounds(unittest.TestCase):
    COOLDOWN = 30.0

    def test_lower_bound_r_zero(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.0]))
        clock.advance(24.0 - 0.001)
        self.assertTrue(b.is_open())
        clock.advance(0.002)
        self.assertTrue(b.is_half_open())

    def test_upper_bound_r_near_one(self):
        clock = FakeClock()
        b = open_breaker(clock, rng=SequenceRng([0.9999999999999999]))
        expected = 30.0 * (0.8 + 0.4 * 0.9999999999999999)
        clock.advance(expected - 0.001)
        self.assertTrue(b.is_open())
        clock.advance(0.002)
        self.assertTrue(b.is_half_open())

    def test_each_open_redraws_jitter(self):
        clock = FakeClock()
        rng = SequenceRng([0.0, 0.9999999999999999, 0.5])
        b = open_breaker(clock, rng=rng)

        # 第一次 open：r=0，24s 即冷却满
        clock.advance(24.0)
        self.assertTrue(b.is_half_open())
        self.assertTrue(b.allow_request())
        b.record_failure()

        # 第二次 open：r≈1，需要约 36s（24s 时仍拒绝）
        clock.advance(24.0)
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())
        expected = 30.0 * (0.8 + 0.4 * 0.9999999999999999)
        clock.advance(expected - 24.0)
        self.assertTrue(b.is_half_open())

    def test_injected_rng_default_is_random_random(self):
        import inspect
        import random

        sig = inspect.signature(CircuitBreaker)
        self.assertIs(sig.parameters["rng"].default, random.random)


if __name__ == "__main__":
    unittest.main()
