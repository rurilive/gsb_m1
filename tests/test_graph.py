"""基线行为测试：锁住 BruteSpan 的朴素连通判断能力。"""

import unittest

from spannex.graph import BruteSpan, SpannError, UnknownNode


class BruteSpanTest(unittest.TestCase):
    def _line(self):
        g = BruteSpan(["a", "b", "c", "d"])
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        return g

    def test_add_node_is_idempotent(self):
        g = BruteSpan(["a"])
        g.add_node("a")
        self.assertEqual(g.nodes(), ["a"])

    def test_rejects_empty_name(self):
        g = BruteSpan()
        with self.assertRaises(SpannError):
            g.add_node("")

    def test_edge_is_undirected(self):
        g = self._line()
        self.assertTrue(g.has_edge("a", "b"))
        self.assertTrue(g.has_edge("b", "a"))

    def test_reached_from_preserves_insertion_order(self):
        g = self._line()
        self.assertEqual(g.reached_from("a"), ["a", "b", "c"])

    def test_disconnected_node_absent(self):
        g = self._line()
        self.assertNotIn("d", g.reached_from("a"))

    def test_reached_from_uses_insertion_order(self):
        g = self._line()
        self.assertEqual(g.reached_from("b"), ["a", "b", "c"])

    def test_connected_across_path(self):
        g = self._line()
        self.assertTrue(g.connected("a", "c"))
        self.assertFalse(g.connected("a", "d"))

    def test_is_connected_over_line(self):
        g = BruteSpan(["a", "b", "c"])
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        self.assertTrue(g.is_connected())
        g.add_node("d")
        self.assertFalse(g.is_connected())

    def test_is_connected_empty_and_single(self):
        self.assertTrue(BruteSpan().is_connected())
        self.assertTrue(BruteSpan(["a"]).is_connected())

    def test_unknown_node_raises(self):
        g = self._line()
        with self.assertRaises(UnknownNode):
            g.reached_from("z")

    def test_unknown_endpoint_raises(self):
        g = self._line()
        with self.assertRaises(UnknownNode):
            g.add_edge("a", "z")


if __name__ == "__main__":
    unittest.main()
