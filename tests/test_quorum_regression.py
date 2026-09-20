"""双主事故的防回归测试。

对应当初事故里复现出来的四类根因：

1. 多数派门槛在构造时按旧成员数算死，扩容后还按老成员数凑票；
2. 活跃判定各看各的本机超时，没人按集群协商好的超时；
3. 旧任期号的心跳照样被采纳，过期 leader 能被心跳"复活"；
4. 摘除成员的旧时间戳一直留在表里参与计票，人数虚高。

每个测试先按当时的时序把现场铺出来，再断言修复后的正确行为。
"""

import unittest

from quorkit.quorum import MemberTable, Quorum


class FakeClock:
    """手动推进的假时钟。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


class TestDynamicMajority(unittest.TestCase):
    def test_majority_follows_membership_growth(self):
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        self.assertEqual(q.majority(), 2)
        cluster.add("n4")
        cluster.add("n5")
        self.assertEqual(q.majority(), 3)

    def test_half_alive_cannot_elect_after_expansion(self):
        clock = FakeClock()
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=clock, timeout=10.0)
        cluster.add("n4")
        cluster.add("n5")
        q.heartbeat("n1", 0.0, 1)
        q.heartbeat("n2", 0.0, 1)
        self.assertIsNone(q.elect())

    def test_majority_shrinks_after_members_removed(self):
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0)
        cluster.remove("n4")
        cluster.remove("n5")
        self.assertEqual(q.majority(), 2)


class TestNegotiatedActiveTimeout(unittest.TestCase):
    def test_active_uses_negotiated_timeout_not_local(self):
        clock = FakeClock()
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=clock, timeout=30.0,
                   config={"heartbeat_timeout": 5.0})
        q.heartbeat("n1", 0.0, 1)
        q.heartbeat("n2", 0.0, 1)
        q.heartbeat("n3", 8.0, 1)
        clock.advance(12.0)
        self.assertEqual(q.active(), {"n3"})

    def test_nodes_share_same_view_of_liveness(self):
        clock = FakeClock()
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        node_a = Quorum(cluster, clock=clock, timeout=30.0,
                        config={"heartbeat_timeout": 5.0})
        node_b = Quorum(cluster, clock=clock, timeout=5.0,
                        config={"heartbeat_timeout": 5.0})
        for node, ts in [("n1", 0.0), ("n2", 0.0),
                         ("n3", 8.0), ("n4", 8.0)]:
            node_a.heartbeat(node, ts, 1)
            node_b.heartbeat(node, ts, 1)
        clock.advance(12.0)
        self.assertEqual(node_a.active(), node_b.active())
        self.assertEqual(node_a.active(), {"n3", "n4"})
        self.assertIsNone(node_a.elect())
        self.assertIsNone(node_b.elect())


class TestStaleTermHeartbeat(unittest.TestCase):
    def test_older_term_heartbeat_is_rejected(self):
        clock = FakeClock()
        q = Quorum(MemberTable(["n1", "n2", "n3"]), clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        for _ in range(5):
            q.elect()
        self.assertEqual(q.term(), 5)
        self.assertFalse(q.heartbeat("n3", 0.0, 2))
        self.assertNotIn("n3", q.active())

    def test_rejected_heartbeat_does_not_refresh_liveness(self):
        clock = FakeClock()
        q = Quorum(MemberTable(["n1", "n2", "n3"]), clock=clock, timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 1)
        q.heartbeat("n2", 0.0, 1)
        q.heartbeat("n3", 0.0, 1)
        self.assertIsNotNone(q.elect())
        self.assertEqual(q.term(), 2)
        clock.advance(5.0)
        self.assertFalse(q.heartbeat("n1", 5.0, 1))
        self.assertTrue(q.heartbeat("n2", 5.0, 2))
        self.assertTrue(q.heartbeat("n3", 5.0, 2))
        clock.advance(6.0)
        self.assertEqual(q.active(), {"n2", "n3"})

    def test_newer_term_heartbeat_advances_term_and_is_accepted(self):
        q = Quorum(MemberTable(["n1", "n2", "n3"]), clock=FakeClock(),
                   timeout=10.0, config={"heartbeat_timeout": 10.0})
        self.assertTrue(q.heartbeat("n1", 0.0, 7))
        self.assertEqual(q.term(), 7)
        self.assertEqual(q.active(), {"n1"})


class TestRemovedMember(unittest.TestCase):
    def test_removed_member_does_not_count_in_active(self):
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        q = Quorum(cluster,
                   clock=FakeClock(), timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        q.heartbeat("n3", 0.0, 0)
        cluster.remove("n3")
        self.assertEqual(q.active(), {"n1", "n2"})

    def test_removed_member_cannot_vote_or_be_elected_on(self):
        cluster = MemberTable(["n1", "n2", "n3", "n4", "n5"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n1", 0.0, 0)
        q.heartbeat("n2", 0.0, 0)
        q.heartbeat("n3", 0.0, 0)
        cluster.remove("n3")
        self.assertIsNone(q.elect())

    def test_heartbeat_after_removal_is_rejected(self):
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        q.heartbeat("n3", 0.0, 0)
        cluster.remove("n3")
        self.assertFalse(q.heartbeat("n3", 1.0, 0))
        self.assertNotIn("n3", q.active())

    def test_readded_member_can_report_alive_again(self):
        cluster = MemberTable(["n1", "n2", "n3"])
        q = Quorum(cluster, clock=FakeClock(), timeout=10.0,
                   config={"heartbeat_timeout": 10.0})
        cluster.remove("n3")
        self.assertFalse(q.heartbeat("n3", 0.0, 0))
        cluster.add("n3")
        self.assertTrue(q.heartbeat("n3", 0.0, 0))
        self.assertIn("n3", q.active())


if __name__ == "__main__":
    unittest.main()
