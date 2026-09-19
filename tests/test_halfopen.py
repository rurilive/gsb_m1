"""CircuitBreaker 三态（half-open）新行为测试。

并发探测用 threading.Event 定节奏，时钟与随机源均注入，
不做真实 sleep，抖动边界靠注入精确断言。
"""

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


def make_half_open(rand=lambda: 0.5, threshold=1, cooldown=30.0):
    """构造一个已进入 half-open 的熔断器，返回 (breaker, clock)。"""
    clock = FakeClock()
    b = CircuitBreaker(threshold=threshold, cooldown=cooldown,
                       clock=clock, rand=rand)
    for _ in range(threshold):
        b.record_failure()
    clock.advance(cooldown)  # 首次熔断按基础冷却计时，期满进 half-open
    return b, clock


class TestHalfOpenPermits(unittest.TestCase):
    def test_only_three_probes_allowed(self):
        b, _ = make_half_open()
        results = [b.allow_request() for _ in range(10)]
        self.assertEqual(results, [True, True, True] + [False] * 7)

    def test_concurrent_probes_never_exceed_permits(self):
        for _ in range(30):  # 多跑几轮，放大竞争窗口
            b, _ = make_half_open()
            start = threading.Event()
            results = []
            results_lock = threading.Lock()

            def probe():
                start.wait()
                allowed = b.allow_request()
                with results_lock:
                    results.append(allowed)

            threads = [threading.Thread(target=probe) for _ in range(10)]
            for t in threads:
                t.start()
            start.set()  # 同一时刻放行全部线程，竞争 3 个名额
            for t in threads:
                t.join()

            self.assertEqual(len(results), 10)
            self.assertEqual(sum(results), 3)  # 名额不超发


class TestHalfOpenClose(unittest.TestCase):
    def test_two_successes_close_and_reset_counts(self):
        b, _ = make_half_open(threshold=2)

        self.assertTrue(b.allow_request())   # 名额 1
        b.record_success()                   # 探测成功 1/2，仍未闭合
        self.assertTrue(b.allow_request())   # 名额 2
        self.assertTrue(b.allow_request())   # 名额 3
        self.assertFalse(b.allow_request())  # 名额耗尽，说明仍在 half-open

        b.record_success()                   # 探测成功 2/2 -> 闭合
        for _ in range(10):                  # 闭合后全量放行，远超 3 个名额
            self.assertTrue(b.allow_request())

        # 连续失败计数已清零：threshold=2，单次失败不会再次熔断
        b.record_failure()
        self.assertFalse(b.is_open())
        self.assertTrue(b.allow_request())


class TestHalfOpenReopen(unittest.TestCase):
    def test_failure_reopens_and_voids_permits(self):
        b, clock = make_half_open(rand=lambda: 0.5)

        self.assertTrue(b.allow_request())   # 发出名额 1
        self.assertTrue(b.allow_request())   # 发出名额 2
        b.record_failure()                   # 探测失败 -> 立即回 open
        self.assertTrue(b.is_open())

        # 已发名额作废：open 期间一律拒绝，漏进来的成功也不改变状态
        self.assertFalse(b.allow_request())
        b.record_success()
        self.assertTrue(b.is_open())

        # 重新计时：rand=0.5 -> 本次冷却 = 30*(0.8+0.4*0.5) = 30s
        clock.advance(29.5)
        self.assertTrue(b.is_open())
        clock.advance(0.5)                   # 恰好满 30s -> 再次 half-open
        # 新一轮名额重新发 3 个
        self.assertEqual([b.allow_request() for _ in range(4)],
                         [True, True, True, False])


class TestJitter(unittest.TestCase):
    def test_first_trip_uses_base_cooldown(self):
        # 首次熔断（非 half-open 回开）按基础冷却计时，行为确定
        clock = FakeClock()
        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock,
                           rand=lambda: 0.0)
        b.record_failure()
        clock.advance(29.5)
        self.assertTrue(b.is_open())
        clock.advance(0.5)                   # 满 30s（而非 0.8*30=24s）
        self.assertTrue(b.allow_request())

    def assert_reopen_cooldown(self, rand_value):
        # 首次熔断(基础冷却30) -> half-open -> 探测失败回 open，
        # 本次冷却 = 30*(0.8+0.4*rand_value)，边界前后逐一断言。
        clock = FakeClock()
        b = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock,
                           rand=lambda: rand_value)
        b.record_failure()
        clock.advance(30.0)                  # half-open
        self.assertTrue(b.allow_request())
        b.record_failure()                   # 探测失败 -> 回 open，抖动冷却
        self.assertTrue(b.is_open())

        expected = 30.0 * (0.8 + 0.4 * rand_value)
        clock.advance(expected - 0.5)        # 边界前 0.5s，仍断开
        self.assertTrue(b.is_open())
        self.assertFalse(b.allow_request())
        clock.advance(0.5)                   # 恰好到边界 -> half-open
        self.assertFalse(b.is_open())
        self.assertTrue(b.allow_request())

    def test_jitter_lower_bound(self):
        self.assert_reopen_cooldown(0.0)         # 冷却 = 30*0.8 = 24s

    def test_jitter_mid(self):
        self.assert_reopen_cooldown(0.5)         # 冷却 = 30*1.0 = 30s

    def test_jitter_upper_bound(self):
        self.assert_reopen_cooldown(1.0 - 1e-9)  # 冷却 -> 30*1.2 = 36s


if __name__ == "__main__":
    unittest.main()
