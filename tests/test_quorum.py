"""quorkit 现有行为的锁定测试。

这些断言描述的是现在就已经成立的行为，一个字都不许动。
"""

import unittest

from quorkit.quorum import MemberTable, Quorum


class FakeClock:
    """手动推进的假时钟，测试里用来踩失联边界。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


def cluster_of(*nodes):
    return MemberTable(nodes)


class TestMajority(unittest.TestCase):
    def test_three_members_need_two(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock())
        self.assertEqual(q.majority(), 2)

    def test_five_members_need_three(self):
        q = Quorum(cluster_of("n1", "n2", "n3", "n4", "n5"), clock=FakeClock())
        self.assertEqual(q.majority(), 3)

    def test_single_member_needs_one(self):
        q = Quorum(cluster_of("n1"), clock=FakeClock())
        self.assertEqual(q.majority(), 1)

    def test_even_cluster_rounds_up(self):
        q = Quorum(cluster_of("n1", "n2", "n3", "n4"), clock=FakeClock())
        self.assertEqual(q.majority(), 3)


class TestActive(unittest.TestCase):
    def test_heartbeat_marks_node_alive(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        self.assertTrue(q.heartbeat("n1", 0.0))
        self.assertEqual(q.active(), {"n1"})

    def test_stale_heartbeat_drops_out(self):
        clock = FakeClock()
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=clock, timeout=10.0)
        q.heartbeat("n1", 0.0)
        clock.advance(20.0)
        self.assertEqual(q.active(), set())

    def test_active_is_a_fresh_snapshot(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0)
        alive = q.active()
        alive.add("bogus")
        self.assertEqual(q.active(), {"n1"})


class TestElect(unittest.TestCase):
    def test_initial_term_is_zero(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock())
        self.assertEqual(q.term(), 0)

    def test_elect_with_full_cluster_alive(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0)
        term = q.elect()
        self.assertIsNotNone(term)
        self.assertEqual(q.term(), term)

    def test_elect_without_any_heartbeat_loses(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        self.assertIsNone(q.elect())

    def test_elect_below_majority_loses(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        q.heartbeat("n1", 0.0)
        self.assertIsNone(q.elect())

    def test_term_strictly_increases(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=10.0)
        for node in ("n1", "n2", "n3"):
            q.heartbeat(node, 0.0)
        first = q.elect()
        second = q.elect()
        self.assertGreater(second, first)


class TestNegotiatedTimeout(unittest.TestCase):
    def test_config_wins_when_negotiated(self):
        q = Quorum(
            cluster_of("n1", "n2", "n3"),
            clock=FakeClock(),
            timeout=1.0,
            config={"heartbeat_timeout": 7.0},
        )
        self.assertEqual(q.negotiated_timeout(), 7.0)

    def test_falls_back_to_local_without_config(self):
        q = Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=3.0)
        self.assertEqual(q.negotiated_timeout(), 3.0)

    def test_invalid_timeout_raises(self):
        with self.assertRaises(ValueError):
            Quorum(cluster_of("n1", "n2", "n3"), clock=FakeClock(), timeout=0)


class TestMemberTable(unittest.TestCase):
    def test_add_and_remove_nodes(self):
        table = MemberTable(("n1",))
        self.assertIn("n1", table)
        table.add("n2")
        self.assertEqual(table.nodes(), {"n1", "n2"})
        table.remove("n1")
        self.assertEqual(table.nodes(), {"n2"})
        self.assertEqual(len(table), 1)

    def test_remove_unknown_is_silent(self):
        table = MemberTable(("n1",))
        table.remove("nope")
        self.assertEqual(table.nodes(), {"n1"})

    def test_nodes_returns_snapshot(self):
        table = MemberTable(("n1",))
        snapshot = table.nodes()
        snapshot.add("bogus")
        self.assertEqual(table.nodes(), {"n1"})


if __name__ == "__main__":
    unittest.main()
