"""Baseline tests for pathlib2.

These tests pin down the *current* behaviour of the naive implementation.
They are the frozen baseline: they must keep passing untouched, and the
iteration is expected to add new tests in a separate file rather than edit
anything here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib2.path import NaivePath, PathError


def sample_graph():
    return {
        "a": [("b", 1), ("c", 4)],
        "b": [("c", 2), ("d", 5)],
        "c": [("d", 1)],
        "d": [],
    }


class NormalizeTest(unittest.TestCase):
    def test_missing_target_becomes_key(self):
        g = NaivePath({"x": [("y", 3)]})
        self.assertIn("y", g.nodes_list())
        self.assertEqual(g.shortest("x", "y"), 3)

    def test_parallel_edges_are_both_kept(self):
        g = NaivePath({"a": [("b", 5), ("b", 2)]})
        self.assertEqual(g.edge_count(), 2)
        self.assertEqual(g.shortest("a", "b"), 2)

    def test_self_loop_is_kept(self):
        g = NaivePath({"a": [("a", 7), ("b", 1)], "b": []})
        self.assertEqual(g.shortest("a", "b"), 1)

    def test_none_adjacency_rejected(self):
        with self.assertRaises(PathError):
            NaivePath(None)

    def test_bad_edge_shape_rejected(self):
        with self.assertRaises(PathError):
            NaivePath({"a": [("b", 1, 2)]})


class ShortestTest(unittest.TestCase):
    def setUp(self):
        self.g = NaivePath(sample_graph())

    def test_source_to_source_is_zero(self):
        self.assertEqual(self.g.shortest("a", "a"), 0)

    def test_direct_and_indirect(self):
        self.assertEqual(self.g.shortest("a", "d"), 4)
        self.assertEqual(self.g.shortest("a", "c"), 3)

    def test_unreachable_returns_none(self):
        g = NaivePath({"a": [], "b": []})
        self.assertIsNone(g.shortest("a", "b"))

    def test_unknown_node_fails_fast(self):
        with self.assertRaises(PathError):
            self.g.shortest("a", "zzz")
        with self.assertRaises(PathError):
            self.g.shortest("zzz", "a")


class DistAllTest(unittest.TestCase):
    def test_distances_match_shortest(self):
        g = NaivePath(sample_graph())
        dist = g.dist_all("a")
        self.assertEqual(dist["a"], 0)
        self.assertEqual(dist["b"], 1)
        self.assertEqual(dist["c"], 3)
        self.assertEqual(dist["d"], 4)

    def test_unreachable_flag(self):
        g = NaivePath({"a": [("b", 1)], "b": [], "c": []})
        dist = g.dist_all("a")
        self.assertEqual(dist["b"], 1)
        self.assertIsNone(dist["c"])

    def test_isolated_source(self):
        g = NaivePath({"a": []})
        dist = g.dist_all("a")
        self.assertEqual(dist, {"a": 0})


class NegativeAndReachTest(unittest.TestCase):
    def test_has_negative_true(self):
        g = NaivePath({"a": [("b", -1)], "b": []})
        self.assertTrue(g.has_negative())

    def test_has_negative_false(self):
        self.assertFalse(NaivePath(sample_graph()).has_negative())

    def test_zero_weight_not_negative(self):
        g = NaivePath({"a": [("b", 0)], "b": []})
        self.assertFalse(g.has_negative())
        self.assertEqual(g.shortest("a", "b"), 0)

    def test_path_exists_variants(self):
        g = NaivePath(sample_graph())
        self.assertTrue(g.path_exists("a", "d"))
        self.assertTrue(g.path_exists("a", "a"))
        self.assertFalse(NaivePath({"a": [], "b": []}).path_exists("a", "b"))


class DeterminismTest(unittest.TestCase):
    def test_two_runs_agree(self):
        first = NaivePath(sample_graph()).dist_all("a")
        second = NaivePath(sample_graph()).dist_all("a")
        self.assertEqual(first, second)

    def test_nodes_sorted(self):
        self.assertEqual(NaivePath(sample_graph()).nodes_list(), ["a", "b", "c", "d"])


if __name__ == "__main__":
    unittest.main()
