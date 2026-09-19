"""bucketd 回归测试：覆盖四个线上事故场景。

运行方式：python3 -m unittest discover -s tests -v
"""
import threading
import unittest

from bucketd import FakeClock, SystemClock, TokenBucket


class ClockBackwardTest(unittest.TestCase):
    """现象 1：时钟回拨不应白送满桶令牌。"""

    def test_backward_jump_does_not_refill(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1.0, burst=5.0, clock=clock)
        for _ in range(5):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())  # 桶已空

        clock.jump_to(700.0)  # 回拨 5 分钟
        self.assertFalse(bucket.try_allow(), "回拨后不应放行")
        self.assertAlmostEqual(bucket.available(), 0.0)

    def test_refill_resumes_after_clock_catches_up(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1.0, burst=5.0, clock=clock)
        for _ in range(5):
            self.assertTrue(bucket.try_allow())

        clock.jump_to(900.0)  # 回拨 100 秒
        clock.advance(100.0)  # 追平回拨前的时刻，期间不应补充
        self.assertAlmostEqual(bucket.available(), 0.0)
        clock.advance(2.0)  # 追平之后恢复匀速补充
        self.assertAlmostEqual(bucket.available(), 2.0)

    def test_backward_jump_does_not_steal_tokens(self):
        clock = FakeClock(start=1000.0)
        bucket = TokenBucket(rate=1.0, burst=10.0, clock=clock)
        clock.jump_to(500.0)
        self.assertAlmostEqual(bucket.available(), 10.0,
                               "回拨不应改变既有余额")


class RecoveryAfterDrainTest(unittest.TestCase):
    """现象 2：桶打空后必须能恢复到 burst 上限。"""

    def test_drained_bucket_recovers(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=0.5, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        self.assertFalse(bucket.try_allow())

        clock.advance(2.0)  # 0.5/s * 2s = 1 个令牌
        self.assertTrue(bucket.try_allow(), "rate<1 的桶打空后也应能恢复")

    def test_recovers_up_to_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)
        for _ in range(10):
            self.assertTrue(bucket.try_allow())
        clock.advance(100.0)  # 远超充满所需时间
        self.assertAlmostEqual(bucket.available(), 10.0)


class ConcurrencyTest(unittest.TestCase):
    """现象 3：并发抢令牌不得超过桶内余额。"""

    def test_no_over_admission_under_contention(self):
        for _ in range(20):  # 多跑几轮放大竞态窗口
            clock = FakeClock(start=0.0)  # 时钟不动，补充恒为 0
            bucket = TokenBucket(rate=1.0, burst=50.0, clock=clock)
            barrier = threading.Barrier(100)
            granted = []
            granted_lock = threading.Lock()

            def worker():
                barrier.wait()
                if bucket.try_allow():
                    with granted_lock:
                        granted.append(1)

            threads = [threading.Thread(target=worker) for _ in range(100)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(sum(granted), 50,
                             "放行数必须严格等于 burst，不得超预算")
            self.assertAlmostEqual(bucket.available(), 0.0)


class LargeBurstAccumulationTest(unittest.TestCase):
    """现象 4：低速率大桶空闲后应能攒到 burst 上限。"""

    def test_large_burst_accumulates_to_cap(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=1.0, burst=1000.0, clock=clock)
        for _ in range(1000):
            self.assertTrue(bucket.try_allow())
        clock.advance(2000.0)  # 空闲 2000s，应攒满 1000
        self.assertAlmostEqual(bucket.available(), 1000.0)

    def test_never_exceeds_burst(self):
        clock = FakeClock(start=0.0)
        bucket = TokenBucket(rate=100.0, burst=1000.0, clock=clock)
        clock.advance(10 ** 6)
        self.assertAlmostEqual(bucket.available(), 1000.0)


class SystemClockTest(unittest.TestCase):
    """SystemClock 应使用单调时钟，不受墙钟回拨影响。"""

    def test_monotonic(self):
        clock = SystemClock()
        samples = [clock.time() for _ in range(100)]
        self.assertEqual(samples, sorted(samples),
                         "SystemClock 读数必须单调不减")


if __name__ == "__main__":
    unittest.main()
