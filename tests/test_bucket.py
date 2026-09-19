"""bucketd 防回归测试：每个线上事故现象对应一组用例。

运行：python3 -m unittest discover -s tests -v
"""
import threading
import time
import unittest

from bucketd import FakeClock, RateLimitError, SystemClock, TokenBucket


class TestClockJumpBackward(unittest.TestCase):
    """现象1：NTP 校时时钟回拨，限流形同虚设、请求全部放行。"""

    def test_backward_jump_does_not_refill(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())

        # 时钟回拨 5 分钟（模拟 NTP 校时），余额不得被重置/补充。
        clock.jump_to(700.0)
        self.assertEqual(bucket.available(), 0.0)
        self.assertFalse(bucket.try_allow())

    def test_backward_jump_then_catch_up(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())

        # 回拨 300 秒再追回到原时刻：净流逝为 0，余额仍为 0。
        clock.jump_to(700.0)
        clock.jump_to(1000.0)
        self.assertEqual(bucket.available(), 0.0)
        # 追回后再真实流逝 1 秒，只补 2 个。
        clock.advance(1.0)
        self.assertAlmostEqual(bucket.available(), 2.0)

    def test_system_clock_uses_monotonic(self):
        import inspect
        import bucketd.clock as clock_mod

        src = inspect.getsource(clock_mod.SystemClock.time)
        self.assertIn("monotonic", src)


class TestRecoveryAfterDrain(unittest.TestCase):
    """现象2：桶被打空后低速率补充，余额永远到不了 1，请求全拒。"""

    def test_low_rate_bucket_recovers(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=0.5, burst=100.0, clock=clock)
        for _ in range(100):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())

        # rate=0.5/s，2 秒应攒出 1 个令牌并放行。
        clock.advance(2.0)
        self.assertTrue(bucket.try_allow())

    def test_capacity_is_burst_not_rate(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            bucket.try_allow()
        clock.advance(5.0)  # 2/s * 5s = 10，应能补满到 burst
        self.assertAlmostEqual(bucket.available(), 10.0)


class TestConcurrentOverspend(unittest.TestCase):
    """现象3：并发瞬间放行数超过桶内余额（check-then-act 竞态）。"""

    def test_no_overspend_under_contention(self):
        for _ in range(20):
            bucket = TokenBucket(rate=0.0001, burst=50.0, clock=SystemClock())
            allowed = 0
            allowed_lock = threading.Lock()
            barrier = threading.Barrier(32)

            def worker():
                nonlocal allowed
                barrier.wait()
                if bucket.try_allow():
                    with allowed_lock:
                        allowed += 1

            threads = [threading.Thread(target=worker) for _ in range(32)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            # 放行总数不得超过 burst（补充速率极低，可忽略）。
            self.assertLessEqual(allowed, 50)

    def test_balance_never_negative(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=5.0, clock=clock)
        for _ in range(5):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())
        self.assertGreaterEqual(bucket.available(), 0.0)


class TestLargeBurstAccumulation(unittest.TestCase):
    """现象4：低速率大桶（burst=1000）余额攒不到配额上限。"""

    def test_accumulates_up_to_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=1000.0, clock=clock)
        for _ in range(1000):
            bucket.try_allow()
        clock.advance(1000.0)  # 1/s * 1000s = 1000 个
        self.assertAlmostEqual(bucket.available(), 1000.0)

    def test_capped_at_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=1000.0, clock=clock)
        clock.advance(10_000.0)  # 空闲再久也不超过 burst
        self.assertAlmostEqual(bucket.available(), 1000.0)


class TestBasicSemantics(unittest.TestCase):
    """既有对外行为保持不变。"""

    def test_refill_rate(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            bucket.try_allow()
        clock.advance(3.0)
        self.assertAlmostEqual(bucket.available(), 6.0)

    def test_allow_raises_when_empty(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=1.0, clock=clock)
        bucket.allow()
        with self.assertRaises(RateLimitError):
            bucket.allow()

    def test_cost_greater_than_balance_rejected(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=10.0, clock=clock)
        self.assertFalse(bucket.try_allow(cost=11.0))
        self.assertTrue(bucket.try_allow(cost=10.0))

    def test_invalid_params_rejected(self):
        with self.assertRaises(ValueError):
            TokenBucket(rate=0, burst=1)
        with self.assertRaises(ValueError):
            TokenBucket(rate=1, burst=-1)

    def test_default_clock_works(self):
        bucket = TokenBucket(rate=100.0, burst=1.0)
        self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())
        time.sleep(0.02)
        self.assertTrue(bucket.try_allow())


if __name__ == "__main__":
    unittest.main()
