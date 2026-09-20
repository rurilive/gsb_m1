"""CircuitBreaker 三态（closed / open / half-open）行为测试。"""

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


def make_half_open(clock, **kwargs):
    """返回一个冷却已结束、下一次访问即进入 half-open 的熔断器。"""
    kwargs.setdefault("r", lambda: 0.5)  # 0.5 -> 抖动因子 1.0，重开冷却仍是 30s
    b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock, **kwargs)
    b.record_failure()
    clock.advance(30.0)
    return b


class TestHalfOpenEntry(unittest.TestCase):
    def test_cooldown_end_enters_half_open_with_limited_probes(self):
        clock = FakeClock()
        b = make_half_open(clock)
        # 冷却结束不再直接闭合：只放行固定 3 个探测名额
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())
        self.assertFalse(b.is_open())

    def test_probe_quota_not_exceeded_under_concurrency(self):
        clock = FakeClock()
        b = make_half_open(clock)
        start = threading.Event()
        results = []
        results_lock = threading.Lock()

        def worker():
            start.wait()
            allowed = b.allow_request()
            with results_lock:
                results.append(allowed)

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 16)
        self.assertEqual(sum(results), 3)  # 名额固定 3 个，并发下不超发


class TestHalfOpenClose(unittest.TestCase):
    def test_two_successes_close_and_reset_counts(self):
        clock = FakeClock()
        b = CircuitBreaker(threshold=2, cooldown=30.0, clock=clock,
                           r=lambda: 0.5)
        b.record_failure()
        b.record_failure()
        clock.advance(30.0)

        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())  # 名额已发完

        b.record_success()
        # 只累计 1 次成功，仍未闭合（若已闭合这里应直接放行）
        self.assertFalse(b.allow_request())
        b.record_success()
        # 累计 2 次成功 -> 闭合，全量放行
        self.assertTrue(b.allow_request())
        self.assertFalse(b.is_open())

        # 闭合时计数清零：阈值 2 需要重新累计连续失败
        b.record_failure()
        self.assertFalse(b.is_open())
        b.record_failure()
        self.assertTrue(b.is_open())


class TestHalfOpenReopen(unittest.TestCase):
    def test_failure_reopens_immediately_and_voids_slots(self):
        clock = FakeClock()
        b = make_half_open(clock)

        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        b.record_success()
        b.record_failure()  # 半开中任一失败 -> 立即回 open
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())

        # 已发名额作废：迟到成功不计数，重开冷却结束后名额重新发 3 个
        b.record_success()
        self.assertTrue(b.is_open())
        clock.advance(30.0)
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertTrue(b.allow_request())
        self.assertFalse(b.allow_request())


class TestReopenJitter(unittest.TestCase):
    def _reopened_breaker(self, clock, r_value):
        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock,
                           r=lambda: r_value)
        b.record_failure()  # 首次熔断：基础冷却 30s
        clock.advance(30.0)
        self.assertTrue(b.allow_request())  # 进入 half-open，发出探测
        b.record_failure()  # 探测失败 -> 重开，冷却按公式加抖动
        self.assertTrue(b.is_open())
        return b

    def test_first_open_uses_base_cooldown_without_jitter(self):
        clock = FakeClock()
        calls = []

        def r():
            calls.append(1)
            return 0.0

        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock, r=r)
        b.record_failure()  # 首次熔断不取抖动
        clock.advance(24.0)  # 抖动下界 0.8*30：若首次即加抖动这里已放行
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())
        clock.advance(6.0)
        self.assertTrue(b.allow_request())
        self.assertEqual(calls, [])  # 首次进 open 未调用 r

    def test_reopen_cooldown_jitter_boundaries(self):
        for r_value, expected in ((0.0, 24.0), (0.25, 27.0),
                                  (0.5, 30.0), (0.75, 33.0)):
            with self.subTest(r_value=r_value):
                clock = FakeClock()
                b = self._reopened_breaker(clock, r_value)
                clock.advance(expected - 0.5)  # 抖动冷却未到期
                self.assertTrue(b.is_open())
                self.assertFalse(b.allow_request())
                clock.advance(0.5)  # 正好到期 -> half-open
                self.assertTrue(b.allow_request())

    def test_jitter_drawn_on_each_reopen(self):
        clock = FakeClock()
        values = iter([0.0, 0.75])
        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock,
                           r=lambda: next(values))
        b.record_failure()
        clock.advance(30.0)
        self.assertTrue(b.allow_request())
        b.record_failure()  # 第一次重开：r=0.0 -> 冷却 24s
        clock.advance(24.0)
        self.assertTrue(b.allow_request())
        b.record_failure()  # 第二次重开：r=0.75 -> 冷却 33s
        clock.advance(32.5)
        self.assertTrue(b.is_open())
        clock.advance(0.5)
        self.assertTrue(b.allow_request())


if __name__ == "__main__":
    unittest.main()
