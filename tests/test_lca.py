"""NaiveLca 现状行为的锁定测试（改造前基线，不许改）。

固定一棵树：
        a
      / | \\
     b  c  d
    / \\    |
   e   f   g
  /
 h
边序列：a-b, a-c, a-d, b-e, b-f, d-g, e-h
"""

import unittest

from lcalib.lca import LcaError, LcaNodeError, NaiveLca

EDGES = [
    ("a", "b"),
    ("a", "c"),
    ("a", "d"),
    ("b", "e"),
    ("b", "f"),
    ("d", "g"),
    ("e", "h"),
]


def build(root=None):
    return NaiveLca(EDGES, root=root)


class TestConstruction(unittest.TestCase):
    def test_root_inferred(self):
        t = build()
        self.assertEqual(t.root, "a")

    def test_root_explicit(self):
        t = NaiveLca([("x", "y")], root="x")
        self.assertEqual(t.root, "x")

    def test_node_count(self):
        self.assertEqual(len(build()), 8)

    def test_contains(self):
        t = build()
        self.assertIn("h", t)
        self.assertNotIn("z", t)

    def test_children_order(self):
        self.assertEqual(build().children("b"), ["e", "f"])

    def test_ambiguous_root_raises(self):
        with self.assertRaises(LcaNodeError):
            NaiveLca([("a", "b"), ("c", "d")])

    def test_unknown_root_raises(self):
        with self.assertRaises(LcaNodeError):
            NaiveLca(EDGES, root="z")

    def test_root_with_parent_raises(self):
        with self.assertRaises(LcaNodeError):
            NaiveLca(EDGES, root="b")

    def test_self_loop_raises(self):
        with self.assertRaises(LcaNodeError):
            NaiveLca([("a", "a")])

    def test_two_parents_raises(self):
        with self.assertRaises(LcaNodeError):
            NaiveLca([("a", "c"), ("b", "c")])

    def test_cycle_raises(self):
        with self.assertRaises(LcaNodeError):
            NaiveLca([("a", "b"), ("b", "c"), ("c", "a")])


class TestParentDepth(unittest.TestCase):
    def test_parent(self):
        t = build()
        self.assertEqual(t.parent("h"), "e")
        self.assertEqual(t.parent("b"), "a")

    def test_parent_of_root_is_none(self):
        self.assertIsNone(build().parent("a"))

    def test_depth(self):
        t = build()
        self.assertEqual(t.depth("a"), 0)
        self.assertEqual(t.depth("b"), 1)
        self.assertEqual(t.depth("h"), 3)

    def test_parent_unknown_raises(self):
        with self.assertRaises(LcaNodeError):
            build().parent("z")

    def test_depth_unknown_raises(self):
        with self.assertRaises(LcaNodeError):
            build().depth("z")


class TestLca(unittest.TestCase):
    def test_same_node(self):
        t = build()
        self.assertEqual(t.lca("h", "h"), "h")

    def test_ancestor_and_descendant(self):
        t = build()
        self.assertEqual(t.lca("a", "h"), "a")
        self.assertEqual(t.lca("h", "a"), "a")

    def test_siblings(self):
        self.assertEqual(build().lca("e", "f"), "b")

    def test_root_and_leaf(self):
        self.assertEqual(build().lca("a", "g"), "a")

    def test_cross_subtree(self):
        t = build()
        self.assertEqual(t.lca("h", "g"), "a")
        self.assertEqual(t.lca("e", "g"), "a")

    def test_deep_pair(self):
        self.assertEqual(build().lca("h", "f"), "b")

    def test_unknown_raises(self):
        t = build()
        with self.assertRaises(LcaNodeError):
            t.lca("h", "z")
        with self.assertRaises(LcaNodeError):
            t.lca("z", "h")


class TestDist(unittest.TestCase):
    def test_same_node(self):
        self.assertEqual(build().dist("c", "c"), 0)

    def test_parent_child(self):
        self.assertEqual(build().dist("a", "b"), 1)

    def test_siblings(self):
        self.assertEqual(build().dist("e", "f"), 2)

    def test_deep_to_root(self):
        self.assertEqual(build().dist("h", "a"), 3)

    def test_cross_subtree(self):
        self.assertEqual(build().dist("h", "g"), 5)

    def test_unknown_raises(self):
        with self.assertRaises(LcaNodeError):
            build().dist("h", "q")


class TestIsAncestor(unittest.TestCase):
    def test_self(self):
        self.assertTrue(build().is_ancestor("c", "c"))

    def test_true_chain(self):
        t = build()
        self.assertTrue(t.is_ancestor("a", "h"))
        self.assertTrue(t.is_ancestor("b", "h"))

    def test_false_sibling(self):
        self.assertFalse(build().is_ancestor("e", "f"))

    def test_false_descendant(self):
        self.assertFalse(build().is_ancestor("h", "b"))

    def test_unknown_raises(self):
        with self.assertRaises(LcaNodeError):
            build().is_ancestor("h", "z")


class TestQueryMany(unittest.TestCase):
    def test_batch_matches_single(self):
        t = build()
        queries = [("h", "f"), ("h", "g"), ("a", "a"), ("e", "g")]
        self.assertEqual(t.query_many(queries), ["b", "a", "a", "a"])

    def test_batch_empty(self):
        self.assertEqual(build().query_many([]), [])


class TestSingleNodeTree(unittest.TestCase):
    def test_lone_root(self):
        t = NaiveLca([], root="only")
        self.assertEqual(t.root, "only")
        self.assertEqual(len(t), 1)
        self.assertIsNone(t.parent("only"))
        self.assertEqual(t.depth("only"), 0)
        self.assertEqual(t.lca("only", "only"), "only")
        self.assertEqual(t.dist("only", "only"), 0)
        self.assertTrue(t.is_ancestor("only", "only"))


class TestExceptionHierarchy(unittest.TestCase):
    def test_node_error_is_lca_error(self):
        self.assertTrue(issubclass(LcaNodeError, LcaError))

    def test_catches_as_base(self):
        with self.assertRaises(LcaError):
            build().lca("a", "zzz")


if __name__ == "__main__":
    unittest.main()
