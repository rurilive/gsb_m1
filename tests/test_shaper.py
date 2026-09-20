"""TokenBucketShaper 新行为测试：整形、排队、超时、多租户公平。

全部使用 ManualClock 推进虚拟时间，不 sleep、不依赖真实时钟。
"""

import unittest

from shapeq.shaper import Request, TokenBucketShaper


class ManualClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make(clock, **kwargs):
    kwargs.setdefault("clock", clock)
    return TokenBucketShaper(**kwargs)


class TestBurstAndRefill(unittest.TestCase):
    def test_burst_up_to_capacity_then_reject(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=3,
                      tenant_rate=1.0, tenant_burst=3)
        for _ in range(3):
            self.assertEqual(shaper.acquire("a").status, Request.GRANTED)
        req = shaper.acquire("a")
        self.assertEqual(req.status, Request.REJECTED)
        self.assertEqual(req.reason, Request.REJECT_FULL)
        s = shaper.stats()
        self.assertEqual((s["granted"], s["rejected"]), (3, 1))
        self.assertEqual(s["tokens"], 0)

    def test_refill_at_configured_rate(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=2.0, shared_burst=2,
                      tenant_rate=2.0, tenant_burst=2)
        shaper.acquire("a")
        shaper.acquire("a")
        self.assertEqual(shaper.acquire("a").status, Request.REJECTED)
        clock.advance(0.499)
        self.assertEqual(shaper.acquire("a").status, Request.REJECTED)
        clock.advance(0.001)
        self.assertEqual(shaper.acquire("a").status, Request.GRANTED)

    def test_refill_is_capped_at_capacity(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=2,
                      tenant_rate=1.0, tenant_burst=2)
        shaper.acquire("a")
        shaper.acquire("a")
        clock.advance(100.0)
        shaper.acquire("a")
        shaper.acquire("a")
        self.assertEqual(shaper.acquire("a").status, Request.REJECTED)

    def test_stats_tokens_floor_and_refresh(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=2,
                      tenant_rate=1.0, tenant_burst=2)
        shaper.acquire("a")
        shaper.acquire("a")
        clock.advance(0.5)
        self.assertEqual(shaper.stats()["tokens"], 0)


class TestQueueAndTimeout(unittest.TestCase):
    def test_excess_waits_then_granted_fifo(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=1,
                      tenant_rate=1.0, tenant_burst=1, timeout=10.0)
        first = shaper.acquire("a")
        q1 = shaper.acquire("a")
        q2 = shaper.acquire("a")
        self.assertEqual(first.status, Request.GRANTED)
        self.assertEqual([q1.status, q2.status],
                         [Request.QUEUED, Request.QUEUED])
        self.assertEqual(shaper.stats()["waiting"], 2)

        clock.advance(1.0)
        shaper.pump()
        self.assertEqual(q1.status, Request.GRANTED)
        self.assertAlmostEqual(q1.waited, 1.0)
        self.assertEqual(q2.status, Request.QUEUED)

        clock.advance(1.0)
        shaper.pump()
        self.assertEqual(q2.status, Request.GRANTED)
        self.assertAlmostEqual(q2.waited, 2.0)
        self.assertEqual(shaper.stats()["waiting"], 0)

    def test_timeout_at_strict_deadline_boundary(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=0.1, shared_burst=1,
                      tenant_rate=0.1, tenant_burst=1, timeout=1.0)
        shaper.acquire("a")
        queued = shaper.acquire("a")
        self.assertEqual(queued.status, Request.QUEUED)

        clock.advance(1.0)
        shaper.pump()
        self.assertEqual(queued.status, Request.QUEUED)

        clock.advance(0.001)
        shaper.pump()
        self.assertEqual(queued.status, Request.REJECTED)
        self.assertEqual(queued.reason, Request.REJECT_TIMEOUT)
        s = shaper.stats()
        self.assertEqual(s["rejected"], 1)
        self.assertEqual(s["timed_out"], 1)
        self.assertEqual(s["waiting"], 0)

    def test_grant_right_at_deadline(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=1,
                      tenant_rate=1.0, tenant_burst=1, timeout=1.0)
        shaper.acquire("a")
        queued = shaper.acquire("a")
        clock.advance(1.0)
        shaper.pump()
        self.assertEqual(queued.status, Request.GRANTED)
        self.assertEqual(queued.reason, None)

    def test_stats_alone_settles_expired(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=0.1, shared_burst=1,
                      tenant_rate=0.1, tenant_burst=1, timeout=1.0)
        shaper.acquire("a")
        queued = shaper.acquire("a")
        clock.advance(2.0)
        s = shaper.stats()
        self.assertEqual(queued.status, Request.REJECTED)
        self.assertEqual(s["waiting"], 0)
        self.assertEqual(s["timed_out"], 1)

    def test_max_queue_rejects_extra(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=0.1, shared_burst=1,
                      tenant_rate=0.1, tenant_burst=1,
                      timeout=100.0, max_queue=1)
        self.assertEqual(shaper.acquire("a").status, Request.GRANTED)
        self.assertEqual(shaper.acquire("a").status, Request.QUEUED)
        full = shaper.acquire("a")
        self.assertEqual(full.status, Request.REJECTED)
        self.assertEqual(full.reason, Request.REJECT_QUEUE_FULL)

    def test_new_request_cannot_jump_queued_one(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=1,
                      tenant_rate=1.0, tenant_burst=1, timeout=10.0)
        shaper.acquire("a")
        older = shaper.acquire("a")
        clock.advance(1.0)
        newer = shaper.acquire("a")
        self.assertEqual(older.status, Request.GRANTED)
        self.assertEqual(newer.status, Request.QUEUED)


class TestMultiTenantFairness(unittest.TestCase):
    def test_saturated_tenant_cannot_take_others_share(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=2.0, shared_burst=4,
                      tenant_rate=2.0, tenant_burst=2, timeout=10.0)
        a = [shaper.acquire("a") for _ in range(4)]
        self.assertEqual([r.status for r in a],
                         [Request.GRANTED, Request.GRANTED,
                          Request.QUEUED, Request.QUEUED])
        b = [shaper.acquire("b") for _ in range(2)]
        self.assertEqual([r.status for r in b],
                         [Request.GRANTED, Request.GRANTED])
        self.assertEqual(shaper.stats()["queues"], {"a": 2})

    def test_round_robin_when_both_queued(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=1,
                      tenant_rate=10.0, tenant_burst=10, timeout=100.0)
        shaper.acquire("a")
        a1 = shaper.acquire("a")
        b1 = shaper.acquire("b")
        self.assertEqual([a1.status, b1.status],
                         [Request.QUEUED, Request.QUEUED])

        clock.advance(1.0)
        shaper.pump()
        self.assertEqual([a1.status, b1.status],
                         [Request.GRANTED, Request.QUEUED])

        clock.advance(1.0)
        shaper.pump()
        self.assertEqual(b1.status, Request.GRANTED)

    def test_queues_drain_together_over_time(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=10.0, shared_burst=10,
                      tenant_rate=1.0, tenant_burst=1, timeout=100.0)
        a_reqs = [shaper.acquire("a") for _ in range(4)]
        b_reqs = [shaper.acquire("b") for _ in range(4)]
        self.assertEqual(sum(r.status == Request.GRANTED for r in a_reqs), 1)
        self.assertEqual(sum(r.status == Request.GRANTED for r in b_reqs), 1)

        for _ in range(3):
            clock.advance(1.0)
            shaper.pump()
            a_done = sum(r.status == Request.GRANTED for r in a_reqs)
            b_done = sum(r.status == Request.GRANTED for r in b_reqs)
            self.assertEqual(a_done, b_done)

        self.assertTrue(all(r.status == Request.GRANTED
                            for r in a_reqs + b_reqs))

    def test_tenant_buckets_are_independent_after_reject(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=2,
                      tenant_rate=1.0, tenant_burst=1, timeout=0.0)
        self.assertEqual(shaper.acquire("a").status, Request.GRANTED)
        self.assertEqual(shaper.acquire("a").status, Request.REJECTED)
        self.assertEqual(shaper.acquire("b").status, Request.GRANTED)


class TestStatsAndValidation(unittest.TestCase):
    def test_stats_returns_fresh_dict(self):
        clock = ManualClock()
        shaper = make(clock, shared_rate=1.0, shared_burst=1)
        snapshot = shaper.stats()
        snapshot["rejected"] = 99
        snapshot["queues"]["x"] = 5
        self.assertEqual(shaper.stats()["rejected"], 0)
        self.assertEqual(shaper.stats()["queues"], {})

    def test_invalid_params_raise(self):
        clock = ManualClock()
        with self.assertRaises(ValueError):
            TokenBucketShaper(shared_rate=0, shared_burst=1, clock=clock)
        with self.assertRaises(ValueError):
            TokenBucketShaper(shared_rate=1, shared_burst=0, clock=clock)
        with self.assertRaises(ValueError):
            TokenBucketShaper(1, 1, tenant_rate=0, clock=clock)
        with self.assertRaises(ValueError):
            TokenBucketShaper(1, 1, tenant_burst=0, clock=clock)
        with self.assertRaises(ValueError):
            TokenBucketShaper(1, 1, timeout=-1.0, clock=clock)
        with self.assertRaises(ValueError):
            TokenBucketShaper(1, 1, max_queue=-1, clock=clock)


if __name__ == "__main__":
    unittest.main()
