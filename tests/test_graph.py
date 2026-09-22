"""WaitGraph 拓扑行为的锁定测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitgraph import WaitGraph  # noqa: E402


class WaitGraphTest(unittest.TestCase):

    def test_add_and_remove_roundtrip(self):
        graph = WaitGraph()
        self.assertIsNone(graph.add_edge(1, 2, "db"))
        self.assertEqual(graph.holders(1), [2])
        self.assertEqual(graph.edge_of(1, "db"), 2)
        self.assertEqual(graph.waiters_of(2), [1])
        self.assertEqual(graph.waits(), [(1, "db", 2)])
        self.assertTrue(graph.remove_edge(1, 2, "db"))
        self.assertEqual(graph.holders(1), [])
        self.assertEqual(graph.waiters_of(2), [])
        self.assertEqual(graph.waits(), [])

    def test_remove_requires_exact_triple(self):
        graph = WaitGraph()
        graph.add_edge(1, 2, "db")
        self.assertFalse(graph.remove_edge(2, 1, "db"))
        self.assertFalse(graph.remove_edge(1, 2, "cache"))
        self.assertEqual(graph.waits(), [(1, "db", 2)])

    def test_overwrite_edge_returns_old_holder(self):
        graph = WaitGraph()
        graph.add_edge(1, 2, "db")
        self.assertEqual(graph.add_edge(1, 3, "db"), 2)
        self.assertEqual(graph.holders(1), [3])
        self.assertEqual(graph.waiters_of(2), [])

    def test_one_waiter_on_several_resources(self):
        graph = WaitGraph()
        graph.add_edge(1, 2, "a")
        graph.add_edge(1, 3, "b")
        self.assertEqual(sorted(graph.holders(1)), [2, 3])
        self.assertEqual(graph.waiters_of(3), [1])

    def test_remove_from_clears_outgoing(self):
        graph = WaitGraph()
        graph.add_edge(1, 2, "a")
        graph.add_edge(1, 3, "b")
        graph.add_edge(2, 1, "c")
        self.assertEqual(graph.waits(), [(1, "a", 2), (1, "b", 3), (2, "c", 1)])
        self.assertEqual(graph.remove_from(1), 2)
        self.assertEqual(graph.holders(1), [])
        self.assertFalse(graph.remove_from(1))

    def test_walk_and_reachable_follow_edges(self):
        graph = WaitGraph()
        graph.add_edge(1, 2, "a")
        graph.add_edge(2, 3, "b")
        self.assertEqual(graph.walk(1), {1, 2, 3})
        self.assertTrue(graph.reachable(1, 3))
        self.assertFalse(graph.reachable(3, 1))
        graph.visits = 0
        graph.reachable(1, 3)
        self.assertGreater(graph.visits, 0)

    def test_nodes_keep_registration_order(self):
        graph = WaitGraph()
        graph.add_edge(5, 7, "a")
        graph.add_edge(3, 5, "b")
        self.assertEqual(graph.nodes(), [5, 7, 3])
        graph.clear()
        self.assertEqual(graph.nodes(), [])


if __name__ == "__main__":
    unittest.main()
