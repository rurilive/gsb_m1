"""TokenBucketShaper 新行为测试：整形、排队与多租户公平。

全部用注入的 ManualClock 精确对齐令牌补充与队列放行点，
不依赖真实时间。
"""

import threading
import unittest

from shapeq.shaper import READY, QUEUED, REJECTED, TokenBucketShaper


class ManualClock:
    """可推进的假时钟，精确控制令牌补充与队列到期。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestTokenBucket(unittest.TestCase):
    def test_burst_absorbed_up_to_capacity(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=3, refill_rate=1.0, clock=clock)
        for _ in range(3):
            self.assertIs(shaper.acquire("a").status, READY)
        stats = shaper.stats()
        self.assertEqual(stats["allowed"], 3)
        self.assertAlmostEqual(stats["tokens"]["a"], 0.0)

    def test_refill_at_configured_rate(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=3, refill_rate=2.0, clock=clock)
        for _ in range(3):
            shaper.acquire("a")
        clock.advance(0.5)               # 补 1 个令牌
        self.assertIs(shaper.acquire("a").status, READY)
        self.assertIs(shaper.acquire("a").status, QUEUED)

    def test_refill_is_capped_at_capacity(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=2, refill_rate=10.0, clock=clock)
        shaper.acquire("a")
        shaper.acquire("a")
        clock.advance(100.0)             # 补再多也不超过桶容量
        for _ in range(2):
            self.assertIs(shaper.acquire("a").status, READY)
        self.assertIs(shaper.acquire("a").status, QUEUED)

    def test_partial_refill_does_not_grant(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0, clock=clock)
        shaper.acquire("a")
        clock.advance(0.5)
        self.assertIs(shaper.acquire("a").status, QUEUED)


class TestQueueShaping(unittest.TestCase):
    def test_overflow_waits_until_refill_point(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0, clock=clock)
        shaper.acquire("a")
        ticket = shaper.acquire("a")
        self.assertIs(ticket.status, QUEUED)
        self.assertAlmostEqual(ticket.ready_at, 1.0)
        self.assertEqual(shaper.stats()["queued"], 1)

        clock.advance(0.999)
        self.assertEqual(shaper.pump(), [])  # 还差一点
        clock.advance(0.001)                 # 恰好到补充点
        done = shaper.pump()
        self.assertEqual(len(done), 1)
        self.assertIs(done[0].status, READY)
        self.assertIs(ticket.status, READY)
        self.assertEqual(shaper.stats()["queued"], 0)

    def test_queue_is_fifo_and_rate_spaced(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, max_wait=10.0, clock=clock
        )
        shaper.acquire("a")
        t1 = shaper.acquire("a")
        t2 = shaper.acquire("a")
        self.assertAlmostEqual(t1.ready_at, 1.0)
        self.assertAlmostEqual(t2.ready_at, 2.0)

        clock.advance(1.0)
        done = shaper.pump()
        self.assertEqual([t.status for t in done], [READY])
        self.assertIs(t1.status, READY)
        self.assertIs(t2.status, QUEUED)

        clock.advance(1.0)
        done = shaper.pump()
        self.assertIs(done[0], t2)
        self.assertIs(t2.status, READY)

    def test_wait_beyond_max_wait_rejected_immediately(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, max_wait=0.5, clock=clock
        )
        shaper.acquire("a")
        ticket = shaper.acquire("a")    # 预计等 1s > 0.5s
        self.assertIs(ticket.status, REJECTED)
        self.assertEqual(shaper.stats()["rejected"], 1)
        self.assertEqual(shaper.stats()["queued"], 0)
        clock.advance(10.0)
        self.assertEqual(shaper.pump(), [])  # 被拒的不入队

    def test_max_wait_zero_rejects_any_overflow(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, max_wait=0.0, clock=clock
        )
        shaper.acquire("a")
        self.assertIs(shaper.acquire("a").status, REJECTED)

    def test_reject_policy_never_queues(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, overflow="reject", clock=clock
        )
        self.assertIs(shaper.acquire("a").status, READY)
        self.assertIs(shaper.acquire("a").status, REJECTED)
        self.assertEqual(shaper.stats()["queued"], 0)
        clock.advance(1.0)
        self.assertEqual(shaper.pump(), [])
        self.assertIs(shaper.acquire("a").status, READY)


class TestTenantFairness(unittest.TestCase):
    def test_tenant_burst_does_not_consume_others(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=2, refill_rate=1.0, clock=clock)
        shaper.acquire("noisy")
        noisy_q1 = shaper.acquire("noisy")
        noisy_q2 = shaper.acquire("noisy")  # 自己排队，不影响别人
        self.assertIs(noisy_q1.status, READY)
        self.assertIs(noisy_q2.status, QUEUED)

        quiet = shaper.acquire("quiet")
        self.assertIs(quiet.status, READY)
        quiet2 = shaper.acquire("quiet")
        self.assertIs(quiet2.status, READY)
        stats = shaper.stats()
        self.assertAlmostEqual(stats["tokens"]["quiet"], 0.0)
        self.assertAlmostEqual(stats["tokens"]["noisy"], 0.0)
        self.assertEqual(stats["queued"], 1)

    def test_quiet_tenant_served_while_noisy_waits(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, max_wait=10.0, clock=clock
        )
        shaper.acquire("noisy")
        for _ in range(3):
            self.assertIs(shaper.acquire("noisy").status, QUEUED)

        clock.advance(2.0)
        # 吵闹租户有两条到期；安静租户此刻照样能拿
        noisy_done = shaper.pump()
        self.assertEqual(len(noisy_done), 2)
        quiet = shaper.acquire("quiet")
        self.assertIs(quiet.status, READY)

        stats = shaper.stats()
        self.assertEqual(stats["queued"], 1)      # noisy 还欠一条
        self.assertEqual(stats["allowed"], 4)    # noisy 1+2 + quiet

    def test_rejection_is_scoped_to_tenant(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(
            capacity=1, refill_rate=1.0, overflow="reject", clock=clock
        )
        self.assertIs(shaper.acquire("noisy").status, READY)
        self.assertIs(shaper.acquire("noisy").status, REJECTED)
        # noisy 被拒不传染，quiet 用自己那份
        self.assertIs(shaper.acquire("quiet").status, READY)
        self.assertEqual(shaper.stats()["rejected"], 1)


class TestStatsAndConfig(unittest.TestCase):
    def test_stats_snapshot_is_independent(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=2, refill_rate=1.0, clock=clock)
        shaper.acquire("a")
        s1 = shaper.stats()
        s1["allowed"] = 99
        s1["tokens"]["a"] = 99.0
        s2 = shaper.stats()
        self.assertEqual(s2["allowed"], 1)
        self.assertNotEqual(s2["tokens"]["a"], 99.0)

    def test_tokens_reflected_in_stats(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=3, refill_rate=2.0, clock=clock)
        shaper.acquire("a")
        clock.advance(1.0)               # -1 + 2 = 3，顶到桶容量
        self.assertAlmostEqual(shaper.stats()["tokens"]["a"], 3.0)

    def test_stats_queued_aggregates_across_tenants(self):
        clock = ManualClock()
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0, clock=clock)
        shaper.acquire("a")
        shaper.acquire("b")
        shaper.acquire("a")
        shaper.acquire("b")
        self.assertEqual(shaper.stats()["queued"], 2)

    def test_clock_is_injectable(self):
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0, clock=lambda: 7.0)
        self.assertIs(shaper.acquire("a").status, READY)

    def test_invalid_capacity_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(capacity=0, refill_rate=1.0)

    def test_invalid_refill_rate_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(capacity=1, refill_rate=0.0)

    def test_invalid_overflow_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(capacity=1, refill_rate=1.0, overflow="block")

    def test_invalid_max_wait_raises(self):
        with self.assertRaises(ValueError):
            TokenBucketShaper(capacity=1, refill_rate=1.0, max_wait=-1.0)

    def test_invalid_token_amount_raises(self):
        shaper = TokenBucketShaper(capacity=1, refill_rate=1.0)
        with self.assertRaises(ValueError):
            shaper.acquire("a", tokens=0)

    def test_concurrent_acquires_keep_accounting_consistent(self):
        shaper = TokenBucketShaper(
            capacity=100, refill_rate=1.0, overflow="reject"
        )

        def hammer():
            for _ in range(300):
                shaper.acquire("t")

        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        s = shaper.stats()
        self.assertEqual(s["allowed"] + s["rejected"], 8 * 300)
        self.assertEqual(s["queued"], 0)


if __name__ == "__main__":
    unittest.main()
