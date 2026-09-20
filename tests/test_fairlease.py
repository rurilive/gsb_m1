"""FairLease 现有行为的锁定测试。"""

import unittest

from fairlease.lease import FairLease


class FakeClock:
    def __init__(self, t=0.0):
        self.now = float(t)

    def __call__(self):
        return self.now


class TestFairLease(unittest.TestCase):
    def make(self, t=0.0, aging=5.0):
        clock = FakeClock(t)
        return FairLease(clock=clock, aging=aging), clock

    def test_ticket_increases_per_request(self):
        fl, _ = self.make()
        self.assertEqual([fl.request("a", 1), fl.request("b", 2)], [1, 2])

    def test_grant_empty_returns_none(self):
        fl, _ = self.make()
        self.assertIsNone(fl.grant())

    def test_smaller_prio_granted_first(self):
        fl, _ = self.make()
        fl.request("slow", 7)
        fl.request("fast", 1)
        self.assertEqual(fl.grant(), "fast")
        self.assertEqual(fl.grant(), "slow")
        self.assertIsNone(fl.grant())

    def test_pending_lists_queued_nodes(self):
        fl, _ = self.make()
        fl.request("a", 3)
        fl.request("b", 1)
        self.assertEqual(set(fl.pending()), {"a", "b"})
        fl.grant()
        self.assertEqual(fl.pending(), ["a"])

    def test_pending_follows_priority_order(self):
        fl, _ = self.make()
        fl.request("c", 9)
        fl.request("b", 5)
        fl.request("a", 1)
        self.assertEqual(fl.pending(), ["a", "b", "c"])

    def test_grant_removes_request_from_queue(self):
        fl, _ = self.make()
        fl.request("a", 1)
        fl.request("b", 1)
        fl.grant()
        self.assertEqual(len(fl.pending()), 1)

    def test_timeout_drops_long_waited_request(self):
        fl, clock = self.make()
        fl.request("a", 1, timeout=2.0)
        clock.now = 9.0
        self.assertIsNone(fl.grant())
        self.assertEqual(fl.pending(), [])

    def test_no_timeout_keeps_request_forever(self):
        fl, clock = self.make()
        fl.request("a", 1, timeout=None)
        clock.now = 1000.0
        self.assertEqual(fl.grant(), "a")

    def test_cancel_unknown_ticket_returns_false(self):
        fl, _ = self.make()
        self.assertFalse(fl.cancel(99))

    def test_cancel_after_grant_returns_false(self):
        fl, _ = self.make()
        ticket = fl.request("a", 1)
        fl.grant()
        self.assertFalse(fl.cancel(ticket))

    def test_clock_is_injectable(self):
        fl, _ = self.make(t=123.0)
        fl.request("a", 1)
        self.assertEqual(fl.grant(), "a")

    def test_invalid_aging_raises(self):
        with self.assertRaises(ValueError):
            FairLease(aging=0)


if __name__ == "__main__":
    unittest.main()
