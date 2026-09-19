"""TokenBucket 防回归测试：覆盖四个线上事故现象及基本语义。"""
import threading
import unittest

from bucketd import FakeClock, RateLimitError, TokenBucket


class BasicSemanticsTest(unittest.TestCase):
    def test_burst_allows_initial_requests_then_rejects(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())

    def test_refill_after_time_passes(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            bucket.try_allow()
        clock.advance(3.0)
        self.assertAlmostEqual(bucket.available(), 6.0)

    def test_allow_raises_when_insufficient(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1.0, burst=1.0, clock=clock)
        bucket.allow()
        with self.assertRaises(RateLimitError):
            bucket.allow()

    def test_invalid_params_rejected(self):
        with self.assertRaises(ValueError):
            TokenBucket(rate=0.0, burst=1.0)
        with self.assertRaises(ValueError):
            TokenBucket(rate=1.0, burst=-1.0)


class ClockJumpBackTest(unittest.TestCase):
    """现象 1：NTP 回拨时钟后限流形同虚设。"""

    def test_backward_jump_does_not_refill(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        self.assertAlmostEqual(bucket.available(), 0.0)

        # 时钟往回拨 5 分钟：不得补充任何令牌。
        clock.jump_to(700.0)
        self.assertAlmostEqual(bucket.available(), 0.0)
        self.assertFalse(bucket.try_allow())

    def test_refill_resumes_after_wall_clock_catches_up(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            bucket.try_allow()
        clock.jump_to(700.0)
        # 墙钟追回到回拨点之前：仍不补充。
        clock.jump_to(999.0)
        self.assertAlmostEqual(bucket.available(), 0.0)
        # 墙钟追平并超过原时刻后，按真实流逝补充。
        clock.jump_to(1002.0)
        self.assertAlmostEqual(bucket.available(), 4.0)


class EmptyBucketRecoveryTest(unittest.TestCase):
    """现象 2：桶被打空后长时间无法恢复。"""

    def test_empty_bucket_recovers_at_configured_rate(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            bucket.try_allow()
        clock.advance(5.0)
        # 5 秒 * 2/s = 10 个，应恢复满。
        self.assertAlmostEqual(bucket.available(), 10.0)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())

    def test_balance_never_goes_negative_under_contention(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1000.0, burst=100.0, clock=clock)
        for _ in range(100):
            bucket.try_allow()
        threads = [threading.Thread(target=lambda: bucket.try_allow()) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertGreaterEqual(bucket.available(), 0.0)


class ConcurrencyBudgetTest(unittest.TestCase):
    """现象 3：压测偶发放行数超过桶内余额。"""

    def test_no_over_admission_under_concurrency(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1.0, burst=50.0, clock=clock)
        granted = []
        guard = threading.Lock()

        def worker():
            if bucket.try_allow():
                with guard:
                    granted.append(1)

        threads = [threading.Thread(target=worker) for _ in range(500)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 时钟未推进，预算只有 burst=50，放行数不得超过 50。
        self.assertEqual(len(granted), 50)
        self.assertAlmostEqual(bucket.available(), 0.0)


class LargeBurstAccumulationTest(unittest.TestCase):
    """现象 4：低速率大桶（burst=1000）余额攒不到上限。"""

    def test_balance_accumulates_up_to_burst(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1.0, burst=1000.0, clock=clock)
        for _ in range(1000):
            bucket.try_allow()
        self.assertAlmostEqual(bucket.available(), 0.0)
        clock.advance(500.0)
        self.assertAlmostEqual(bucket.available(), 500.0)
        clock.advance(10000.0)
        # 空闲再久也不超过 burst 上限。
        self.assertAlmostEqual(bucket.available(), 1000.0)


if __name__ == "__main__":
    unittest.main()
