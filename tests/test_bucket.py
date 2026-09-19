"""TokenBucket 防回归测试：覆盖四个线上事故场景。"""
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bucketd import FakeClock, RateLimitError, TokenBucket


class ClockRollbackTest(unittest.TestCase):
    """现象1: NTP 回拨时钟后限流形同虚设。"""

    def test_backward_jump_does_not_refill(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())
        clock.jump_to(700.0)
        self.assertFalse(bucket.try_allow(), "回拨后不应白送令牌")
        self.assertEqual(bucket.available(), 0.0)

    def test_backward_jump_not_double_credited(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        clock.jump_to(900.0)
        clock.jump_to(1005.0)
        self.assertAlmostEqual(bucket.available(), 10.0)


class CapacityRecoveryTest(unittest.TestCase):
    """现象2: 桶被打空后永远缓不过来（容量被错配为 rate）。"""

    def test_empty_bucket_recovers_to_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        clock.advance(5.0)
        self.assertAlmostEqual(bucket.available(), 10.0)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())

    def test_cost_above_rate_eventually_affordable(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        self.assertTrue(bucket.try_allow(10))
        self.assertFalse(bucket.try_allow(10))
        clock.advance(5.0)
        self.assertTrue(bucket.try_allow(10), "攒到 burst 后大额请求应放行")


class ConcurrencyTest(unittest.TestCase):
    """现象3: 压测偶发放行超预算（check-then-act 竞态）。"""

    def test_no_overcommit_under_contention(self):
        for _ in range(20):
            clock = FakeClock(start=0.0)
            bucket = TokenBucket(rate=1.0, burst=100.0, clock=clock)
            allowed = 0
            count_lock = threading.Lock()

            def worker():
                nonlocal allowed
                local = 0
                for _ in range(50):
                    if bucket.try_allow():
                        local += 1
                with count_lock:
                    allowed += local

            threads = [threading.Thread(target=worker) for _ in range(16)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(allowed, 100, "放行总数不得超过桶内余额")
            self.assertGreaterEqual(bucket.available(), 0.0, "余额不得为负")


class AccumulationTest(unittest.TestCase):
    """现象4: 低速率大桶（burst=1000）余额攒不到上限。"""

    def test_idle_accumulates_up_to_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=1000.0, clock=clock)
        for _ in range(1000):
            bucket.try_allow()
        clock.advance(1000.0)
        self.assertAlmostEqual(bucket.available(), 1000.0)

    def test_never_exceeds_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=100.0, burst=1000.0, clock=clock)
        clock.advance(10000.0)
        self.assertAlmostEqual(bucket.available(), 1000.0)


class BasicBehaviorTest(unittest.TestCase):
    """既有对外行为保持不变。"""

    def test_demo_flow(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())
        clock.advance(3.0)
        self.assertAlmostEqual(bucket.available(), 6.0)
        for _ in range(3):
            self.assertTrue(bucket.try_allow())
        self.assertTrue(bucket.try_allow(3))
        self.assertFalse(bucket.try_allow(5))

    def test_allow_raises_when_insufficient(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=2.0, clock=clock)
        bucket.allow(2)
        with self.assertRaises(RateLimitError):
            bucket.allow()

    def test_invalid_params_rejected(self):
        with self.assertRaises(ValueError):
            TokenBucket(rate=0, burst=1)
        with self.assertRaises(ValueError):
            TokenBucket(rate=1, burst=-1)


if __name__ == "__main__":
    unittest.main()
