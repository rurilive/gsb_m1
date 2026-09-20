"""四个线上缺陷修复后的行为回归测试。

与基线 tests/test_fairlease.py 分开存放，基线文件保持原样不动。
覆盖：老化防饿死、同优先级先来后到、撤单立即出队、超时边界。
"""

import unittest

from fairlease.lease import FairLease


class FakeClock:
    def __init__(self, t=0.0):
        self.now = float(t)

    def __call__(self):
        return self.now


class TestAgingNoStarvation(unittest.TestCase):
    def make(self, t=0.0, aging=5.0):
        clock = FakeClock(t)
        return FairLease(clock=clock, aging=aging), clock

    def test_low_prio_served_once_aged_under_sustained_load(self):
        # 现场一：每拍都来一个高优先级，等够 aging 的低优先级必须拿到一拍
        fl, clock = self.make(aging=5.0)
        fl.request("batch", 9)
        served = []
        for t in range(1, 7):
            clock.now = float(t)
            fl.request(f"hot{t}", 0)
            served.append(fl.grant())
        self.assertEqual(served,
                         ["hot1", "hot2", "hot3", "hot4", "batch", "hot5"])
        self.assertNotIn("batch", fl.pending())

    def test_aged_requests_keep_fifo_order(self):
        # 老化组内部严格先来后到，与优先级、节点名都无关
        fl, clock = self.make(aging=2.0)
        fl.request("zeta", 9)
        clock.now = 1.0
        fl.request("alpha", 1)
        clock.now = 3.0
        self.assertEqual(fl.pending(), ["zeta", "alpha"])

    def test_newly_aged_low_prio_jumps_ahead_of_fresh_high_prio(self):
        fl, clock = self.make(aging=2.0)
        fl.request("batch", 9)
        clock.now = 2.0
        fl.request("hot", 0)
        self.assertEqual(fl.grant(), "batch")
        self.assertEqual(fl.grant(), "hot")

    def test_unaged_requests_still_follow_priority(self):
        fl, clock = self.make(aging=10.0)
        fl.request("low", 9)
        clock.now = 1.0
        fl.request("high", 0)
        self.assertEqual(fl.pending(), ["high", "low"])

    def test_finite_wait_bound_under_continuous_high_prio_arrivals(self):
        # 久等的请求在有限时间内一定被发放：持续涌入高优先级时，
        # batch 在等够 aging 后的下一轮即被服务
        fl, clock = self.make(aging=3.0)
        fl.request("batch", 9)
        granted = None
        for t in range(1, 20):
            clock.now = float(t)
            fl.request(f"hot{t}", 0)
            node = fl.grant()
            if node == "batch":
                granted = t
                break
        self.assertEqual(granted, 3)


class TestSamePriorityFifo(unittest.TestCase):
    def make(self):
        return FairLease(clock=FakeClock())

    def test_fifo_within_same_priority_regardless_of_node_name(self):
        fl = self.make()
        fl.request("zeta", 2)
        fl.request("alpha", 2)
        fl.request("mid", 2)
        self.assertEqual(fl.pending(), ["zeta", "alpha", "mid"])
        self.assertEqual([fl.grant(), fl.grant(), fl.grant()],
                         ["zeta", "alpha", "mid"])

    def test_arrival_order_preserved_across_clock_ticks(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=100.0)
        tickets = []
        for t in range(5):
            clock.now = float(t)
            tickets.append(fl.request(f"n{t}", 4))
        self.assertEqual(tickets, [1, 2, 3, 4, 5])
        self.assertEqual(fl.pending(), ["n0", "n1", "n2", "n3", "n4"])


class TestCancelSemantics(unittest.TestCase):
    def test_cancelled_request_leaves_queue_immediately(self):
        fl = FairLease(clock=FakeClock())
        ticket = fl.request("ghost", 0)
        fl.request("real", 5)
        self.assertTrue(fl.cancel(ticket))
        self.assertEqual(fl.pending(), ["real"])
        self.assertEqual(fl.grant(), "real")

    def test_cancel_middle_request_does_not_consume_grant(self):
        fl = FairLease(clock=FakeClock())
        fl.request("a", 1)
        middle = fl.request("b", 1)
        fl.request("c", 1)
        self.assertTrue(fl.cancel(middle))
        self.assertEqual([fl.grant(), fl.grant()], ["a", "c"])
        self.assertIsNone(fl.grant())

    def test_double_cancel_returns_false(self):
        fl = FairLease(clock=FakeClock())
        ticket = fl.request("a", 1)
        self.assertTrue(fl.cancel(ticket))
        self.assertFalse(fl.cancel(ticket))

    def test_cancel_after_grant_returns_false(self):
        fl = FairLease(clock=FakeClock())
        ticket = fl.request("a", 1)
        fl.grant()
        self.assertFalse(fl.cancel(ticket))

    def test_cancel_unknown_ticket_returns_false(self):
        fl = FairLease(clock=FakeClock())
        self.assertFalse(fl.cancel(123))


class TestTimeoutBoundary(unittest.TestCase):
    def test_exactly_at_timeout_is_still_valid(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=100.0)
        fl.request("edge", 1, timeout=2.0)
        clock.now = 2.0
        self.assertEqual(fl.pending(), ["edge"])
        self.assertEqual(fl.grant(), "edge")

    def test_just_beyond_timeout_is_dropped(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=100.0)
        fl.request("late", 1, timeout=2.0)
        clock.now = 2.0000001
        self.assertEqual(fl.pending(), [])
        self.assertIsNone(fl.grant())

    def test_boundary_request_can_still_be_served_ahead_of_later_arrivals(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=100.0)
        fl.request("edge", 1, timeout=2.0)
        clock.now = 2.0
        fl.request("fresh", 5)
        self.assertEqual(fl.grant(), "edge")
        self.assertEqual(fl.grant(), "fresh")

    def test_timeout_smaller_than_aging_uses_strict_greater_than(self):
        clock = FakeClock(0.0)
        fl = FairLease(clock=clock, aging=5.0)
        fl.request("edge", 9, timeout=2.0)
        clock.now = 2.0
        # 卡点有效；虽未老化，仍是队列里唯一的请求
        self.assertEqual(fl.grant(), "edge")


if __name__ == "__main__":
    unittest.main()
