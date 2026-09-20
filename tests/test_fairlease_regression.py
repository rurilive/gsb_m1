"""四个线上缺陷的回归测试：老化防饿死、同级 FIFO、撤单即时、超时边界。

基线测试 tests/test_fairlease.py 锁定既有行为，本文件只覆盖修复点。
"""

import unittest

from fairlease.lease import FairLease


class FakeClock:
    def __init__(self, t=0.0):
        self.now = float(t)

    def __call__(self):
        return self.now


class AgingTests(unittest.TestCase):
    def make(self, t=0.0, aging=5.0):
        clock = FakeClock(t)
        return FairLease(clock=clock, aging=aging), clock

    def test_low_priority_served_once_aged_under_continuous_load(self):
        fl, clock = self.make()
        fl.request("batch", 9)
        served = []
        for t in range(1, 7):
            clock.now = float(t)
            fl.request("hot%d" % t, 0)
            served.append(fl.grant())
        self.assertEqual(served,
                         ["hot1", "hot2", "hot3", "hot4", "batch", "hot5"])
        self.assertNotIn("batch", fl.pending())

    def test_not_aged_just_before_aging_window(self):
        fl, clock = self.make()
        fl.request("batch", 9)
        clock.now = 4.9
        fl.request("hot", 0)
        self.assertEqual(fl.grant(), "hot")
        self.assertEqual(fl.pending(), ["batch"])

    def test_aged_exactly_at_aging_boundary(self):
        fl, clock = self.make()
        fl.request("batch", 9)
        clock.now = 5.0
        fl.request("hot", 0)
        self.assertEqual(fl.grant(), "batch")

    def test_aged_requests_keep_fifo_even_across_priorities(self):
        fl, clock = self.make()
        fl.request("low", 9)
        fl.request("high", 0)
        clock.now = 5.5
        self.assertEqual(fl.pending(), ["low", "high"])
        self.assertEqual([fl.grant(), fl.grant()], ["low", "high"])

    def test_fresh_high_priority_still_precedes_fresh_low_priority(self):
        fl, clock = self.make()
        fl.request("low", 9)
        fl.request("high", 0)
        clock.now = 1.0
        self.assertEqual(fl.pending(), ["high", "low"])

    def test_new_arrival_cannot_jump_ahead_of_aged_request(self):
        fl, clock = self.make()
        fl.request("old-low", 9)
        clock.now = 6.0
        fl.request("brand-new-high", 0)
        self.assertEqual(fl.grant(), "old-low")


class SamePriorityFifoTests(unittest.TestCase):
    def test_same_priority_follows_submission_order(self):
        fl = FairLease()
        fl.request("zeta", 2)
        fl.request("alpha", 2)
        self.assertEqual([fl.grant(), fl.grant()], ["zeta", "alpha"])

    def test_pending_same_priority_follows_submission_order(self):
        fl = FairLease()
        for node in ("n3", "n1", "n2"):
            fl.request(node, 4)
        self.assertEqual(fl.pending(), ["n3", "n1", "n2"])

    def test_ticket_order_within_priority_after_higher_served(self):
        fl = FairLease()
        fl.request("z-p1", 1)
        fl.request("a-p0", 0)
        fl.request("b-p0", 0)
        self.assertEqual([fl.grant(), fl.grant(), fl.grant()],
                         ["a-p0", "b-p0", "z-p1"])


class CancelTests(unittest.TestCase):
    def test_cancelled_request_leaves_queue_immediately(self):
        fl = FairLease()
        doomed = fl.request("ghost", 0)
        fl.request("real", 5)
        self.assertTrue(fl.cancel(doomed))
        self.assertEqual(fl.pending(), ["real"])
        self.assertEqual(fl.grant(), "real")
        self.assertIsNone(fl.grant())

    def test_cancel_middle_preserves_fifo(self):
        fl = FairLease()
        fl.request("a", 1)
        middle = fl.request("b", 1)
        fl.request("c", 1)
        self.assertTrue(fl.cancel(middle))
        self.assertEqual([fl.grant(), fl.grant()], ["a", "c"])
        self.assertFalse(fl.cancel(middle))

    def test_cancel_unknown_or_served_ticket_returns_false(self):
        fl = FairLease()
        self.assertFalse(fl.cancel(99))
        ticket = fl.request("a", 1)
        fl.grant()
        self.assertFalse(fl.cancel(ticket))

    def test_cancel_only_pending_request_empties_queue(self):
        fl = FairLease()
        ticket = fl.request("solo", 0)
        self.assertTrue(fl.cancel(ticket))
        self.assertEqual(fl.pending(), [])
        self.assertIsNone(fl.grant())


class TimeoutBoundaryTests(unittest.TestCase):
    def test_exactly_at_timeout_is_still_valid(self):
        clock = FakeClock()
        fl = FairLease(clock=clock)
        fl.request("edge", 1, timeout=2.0)
        clock.now = 2.0
        self.assertEqual(fl.pending(), ["edge"])
        self.assertEqual(fl.grant(), "edge")

    def test_just_past_timeout_is_dropped(self):
        clock = FakeClock()
        fl = FairLease(clock=clock)
        fl.request("late", 1, timeout=2.0)
        clock.now = 2.5
        self.assertEqual(fl.pending(), [])
        self.assertIsNone(fl.grant())

    def test_tiny_overflow_is_also_dropped(self):
        clock = FakeClock()
        fl = FairLease(clock=clock)
        fl.request("late", 1, timeout=2.0)
        clock.now = 2.0000001
        self.assertEqual(fl.pending(), [])

    def test_expired_request_does_not_block_later_one(self):
        clock = FakeClock()
        fl = FairLease(clock=clock)
        fl.request("stale", 0, timeout=1.0)
        fl.request("alive", 5)
        clock.now = 3.0
        self.assertEqual(fl.grant(), "alive")

    def test_none_timeout_ignores_wall_clock(self):
        clock = FakeClock()
        fl = FairLease(clock=clock, aging=1.0)
        fl.request("forever", 9)
        clock.now = 9999.0
        self.assertEqual(fl.grant(), "forever")


if __name__ == "__main__":
    unittest.main()
