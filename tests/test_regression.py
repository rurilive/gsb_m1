"""quorkit 法定人数漂移问题的防回归测试。

每一类对应一次线上双主事故里暴露的根因：
- 多数派门槛必须按当前在册成员动态算；
- 活跃判定必须走集群协商的超时，而不是本机配置；
- 任期严格往前，旧任期的心跳一律不认；
- 被摘除的成员立刻退出计票。
"""

import unittest

from quorkit.quorum import MemberTable, Quorum


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


class TestDynamicMajority(unittest.TestCase):
    def test_majority_grows_after_scale_up(self):
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=FakeClock())
        self.assertEqual(q.majority(), 2)
        cluster.add("n4")
        cluster.add("n5")
        self.assertEqual(q.majority(), 3)

    def test_majority_shrinks_after_removal(self):
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        q = Quorum(cluster, clock=FakeClock())
        cluster.remove("n4")
        cluster.remove("n5")
        self.assertEqual(q.majority(), 2)

    def test_elect_uses_current_membership(self):
        clock = FakeClock()
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=clock, timeout=10.0)
        cluster.add("n4")
        cluster.add("n5")
        q.heartbeat("n1", 0.0)
        q.heartbeat("n2", 0.0)
        self.assertIsNone(q.elect())
        q.heartbeat("n3", 0.0, q.term())
        self.assertIsNotNone(q.elect())


class TestNegotiatedTimeoutGovernsActive(unittest.TestCase):
    def test_active_uses_negotiated_not_local_timeout(self):
        clock = FakeClock()
        q = Quorum(
            MemberTable(["n1", "n2", "n3"]),
            clock=clock,
            timeout=30.0,
            config={"heartbeat_timeout": 5.0},
        )
        q.heartbeat("n1", 0.0)
        clock.advance(10.0)
        self.assertEqual(q.active(), set())

    def test_nodes_agree_on_active_set_despite_local_timeouts(self):
        clock = FakeClock()
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        config = {"heartbeat_timeout": 5.0}
        node_a = Quorum(cluster, clock=clock, timeout=30.0, config=config)
        node_b = Quorum(cluster, clock=clock, timeout=5.0, config=config)
        for node, ts in [("n1", 0.0), ("n2", 0.0), ("n3", 8.0), ("n4", 8.0)]:
            node_a.heartbeat(node, ts, 1)
            node_b.heartbeat(node, ts, 1)
        clock.advance(12.0)
        self.assertEqual(node_a.active(), node_b.active())
        self.assertIsNone(node_a.elect())
        self.assertIsNone(node_b.elect())


class TestTermMonotonicity(unittest.TestCase):
    def test_stale_term_heartbeat_rejected(self):
        q = Quorum(MemberTable(["n1", "n2", "n3"]), clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        q.elect()
        q.elect()
        self.assertFalse(q.heartbeat("n3", 0.0, 1))
        self.assertEqual(q.active(), {"n1", "n2"})

    def test_newer_term_heartbeat_accepted_and_adopted(self):
        q = Quorum(MemberTable(["n1", "n2", "n3"]), clock=FakeClock(), timeout=10.0)
        q.elect()
        self.assertTrue(q.heartbeat("n2", 0.0, 7))
        self.assertEqual(q.term(), 7)

    def test_term_never_goes_backwards(self):
        q = Quorum(MemberTable(["n1", "n2", "n3"]), clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0, 5)
        q.heartbeat("n2", 0.0, 3)
        self.assertEqual(q.term(), 5)


class TestRemovedMembersStopCounting(unittest.TestCase):
    def test_removed_member_drops_out_of_active(self):
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0)
        q.heartbeat("n2", 0.0)
        cluster.remove("n2")
        self.assertEqual(q.active(), {"n1"})

    def test_removed_member_cannot_tip_election(self):
        clock = FakeClock()
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        q = Quorum(cluster, clock=clock, timeout=10.0)
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0)
        cluster.remove("n3")
        self.assertIsNone(q.elect())

    def test_heartbeat_from_non_member_does_not_count(self):
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0)
        q.heartbeat("ghost", 0.0)
        self.assertEqual(q.active(), {"n1"})
        self.assertIsNone(q.elect())


if __name__ == "__main__":
    unittest.main()
