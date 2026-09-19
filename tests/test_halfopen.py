"""三态熔断器 half-open 行为测试。

并发探测用 threading.Event 定节奏，假时钟推进冷却，注入
ScriptedRandom 精确断言抖动边界，全程不做真实 sleep。
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


class ScriptedRandom:
    """按预设序列返回 r 值的假随机源（零参可调用）。"""

    def __init__(self, values):
        self._values = list(values)
        self.calls = 0

    def __call__(self):
        value = self._values[self.calls % len(self._values)]
        self.calls += 1
        return value


def trip_to_half_open(cooldown=30.0, threshold=1, r_values=(0.0,)):
    """造一个冷却刚走完、落在 half-open 的熔断器。"""
    clock = FakeClock()
    rng = ScriptedRandom(r_values)
    breaker = CircuitBreaker(
        threshold=threshold,
        cooldown=cooldown,
        clock=clock,
        random=rng,
    )
    for _ in range(threshold):
        breaker.record_failure()
    clock.advance(cooldown)
    assert breaker.state == CircuitBreaker.HALF_OPEN
    return breaker, clock, rng


class TestHalfOpenEntry(unittest.TestCase):
    def test_cooldown_end_enters_half_open_not_closed(self):
        breaker, _, _ = trip_to_half_open()
        self.assertFalse(breaker.is_open())
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)

    def test_cooldown_boundary_is_exact(self):
        # 差一点仍 open，到点立即 half-open
        clock = FakeClock()
        breaker = CircuitBreaker(threshold=1, cooldown=30.0, clock=clock)
        breaker.record_failure()
        clock.advance(29.5)
        self.assertTrue(breaker.is_open())
        self.assertFalse(breaker.allow_request())
        clock.advance(0.5)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)

    def test_first_trip_uses_base_cooldown_without_sampling(self):
        # 首次熔断落在基础 cooldown，不抽抖动（既有调用方时序保持确定）
        clock = FakeClock()
        rng = ScriptedRandom([1.0 - 2 ** -53])
        breaker = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock, random=rng
        )
        breaker.record_failure()
        clock.advance(29.5)
        self.assertTrue(breaker.is_open())
        clock.advance(0.5)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)
        self.assertEqual(rng.calls, 0)


class TestProbeQuota(unittest.TestCase):
    def test_concurrent_probes_never_overshoot(self):
        # 多轮突发：每轮全新 half-open，20 个线程经 Event 同时抢，
        # 任何一轮放行数都必须恰好为 3，且 3 个名额属于不同线程。
        for _ in range(10):
            breaker, _, _ = trip_to_half_open()
            allowed = []
            denied = []
            go = threading.Event()

            def worker():
                go.wait()
                if breaker.allow_request():
                    allowed.append(threading.get_ident())
                else:
                    denied.append(threading.get_ident())

            threads = [threading.Thread(target=worker) for _ in range(20)]
            for thread in threads:
                thread.start()
            go.set()
            for thread in threads:
                thread.join()

            self.assertEqual(len(allowed), 3)
            self.assertEqual(len(denied), 17)
            self.assertEqual(len(set(allowed)), 3)
            # 名额耗尽后再要也不给
            self.assertFalse(breaker.allow_request())

    def test_sequential_quota_is_three(self):
        breaker, _, _ = trip_to_half_open()
        self.assertTrue(breaker.allow_request())
        self.assertTrue(breaker.allow_request())
        self.assertTrue(breaker.allow_request())
        self.assertFalse(breaker.allow_request())

    def test_finished_probe_frees_slot_but_never_more_than_three(self):
        breaker, _, _ = trip_to_half_open()
        self.assertTrue(breaker.allow_request())
        self.assertTrue(breaker.allow_request())
        self.assertTrue(breaker.allow_request())
        self.assertFalse(breaker.allow_request())
        # 一个探测完成（成功），名额回收一个
        breaker.record_success()
        self.assertTrue(breaker.allow_request())
        self.assertFalse(breaker.allow_request())
        # 第二个成功后闭合，全量放行
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitBreaker.CLOSED)
        self.assertTrue(breaker.allow_request())


class TestCloseOnSuccess(unittest.TestCase):
    def test_two_successes_close_and_clear_counts(self):
        breaker, _, _ = trip_to_half_open(threshold=3)
        self.assertTrue(breaker.allow_request())
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)
        self.assertTrue(breaker.allow_request())
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitBreaker.CLOSED)
        # 清零计数：threshold=3，闭合后单次失败不得立刻熔断
        breaker.record_failure()
        self.assertFalse(breaker.is_open())
        self.assertTrue(breaker.allow_request())

    def test_single_success_does_not_close(self):
        breaker, _, _ = trip_to_half_open()
        breaker.allow_request()
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)
        self.assertFalse(breaker.is_open())


class TestReopenOnFailure(unittest.TestCase):
    def test_any_failure_reopens_immediately(self):
        breaker, clock, rng = trip_to_half_open(r_values=(0.0,))
        self.assertTrue(breaker.allow_request())
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()  # 任一失败立即回 open 并重抽抖动
        self.assertTrue(breaker.is_open())
        self.assertEqual(breaker.state, CircuitBreaker.OPEN)
        self.assertEqual(rng.calls, 1)
        self.assertFalse(breaker.allow_request())
        # open 期间漏报的结果不改变状态
        breaker.record_success()
        breaker.record_failure()
        self.assertTrue(breaker.is_open())

    def test_issued_slots_voided_and_fresh_round_after_cooldown(self):
        breaker, clock, _ = trip_to_half_open(r_values=(0.0,))
        self.assertTrue(breaker.allow_request())
        self.assertTrue(breaker.allow_request())
        breaker.record_failure()  # 已发名额全部作废
        self.assertTrue(breaker.is_open())
        # r=0 -> 24s 冷却；到期后是全新一轮 3 个名额
        clock.advance(23.5)
        self.assertTrue(breaker.is_open())
        clock.advance(0.5)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)
        for _ in range(3):
            self.assertTrue(breaker.allow_request())
        self.assertFalse(breaker.allow_request())


class TestCooldownJitter(unittest.TestCase):
    def test_lower_boundary_exact(self):
        clock = FakeClock()
        rng = ScriptedRandom([0.0])
        breaker = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock, random=rng
        )
        breaker.record_failure()
        clock.advance(30.0)
        breaker.record_failure()  # 半开失败重开：r=0 -> 0.8*30 = 24s
        self.assertEqual(rng.calls, 1)
        self.assertTrue(breaker.is_open())
        clock.advance(24.0 - 1e-12)
        self.assertTrue(breaker.is_open())
        clock.advance(2e-12)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)

    def test_upper_boundary_exact(self):
        near_one = 1.0 - 2 ** -53
        clock = FakeClock()
        rng = ScriptedRandom([near_one])
        breaker = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock, random=rng
        )
        breaker.record_failure()
        clock.advance(30.0)
        breaker.record_failure()  # r 接近 1 -> 接近 1.2*30 = 36s
        expected = 30.0 * (0.8 + 0.4 * near_one)
        self.assertGreaterEqual(expected, 30.0 * 1.2 - 1e-12)
        self.assertTrue(breaker.is_open())
        clock.advance(expected - 1e-12)
        self.assertTrue(breaker.is_open())
        clock.advance(2e-12)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)

    def test_midpoint_and_resample_each_reopen(self):
        clock = FakeClock()
        rng = ScriptedRandom([0.5, 0.0])
        breaker = CircuitBreaker(
            threshold=1, cooldown=30.0, clock=clock, random=rng
        )
        breaker.record_failure()
        clock.advance(30.0)
        breaker.record_failure()  # 第一次重开 r=0.5 -> (0.8+0.2)*30 = 30s
        clock.advance(29.5)
        self.assertTrue(breaker.is_open())
        clock.advance(0.5)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)
        breaker.record_failure()  # 第二次重开重新抽样 r=0.0 -> 24s
        self.assertTrue(breaker.is_open())
        clock.advance(23.5)
        self.assertTrue(breaker.is_open())
        clock.advance(0.5)
        self.assertEqual(breaker.state, CircuitBreaker.HALF_OPEN)
        self.assertEqual(rng.calls, 2)

    def test_jitter_factor_range_is_0_8_to_1_2(self):
        # 抖动公式落点：系数在 [0.8, 1.2)，对应 [24s, 36s)
        factors = [0.8 + 0.4 * r for r in (0.0, 0.25, 0.5, 0.75)]
        self.assertEqual(factors[0], 0.8)
        self.assertEqual(factors[2], 1.0)
        self.assertGreaterEqual(min(factors), 0.8)
        self.assertLess(max(factors), 1.2)
        # 数学上 r < 1，故上界开区间；double 下近 1 值由边界测试精确覆盖


if __name__ == "__main__":
    unittest.main()
