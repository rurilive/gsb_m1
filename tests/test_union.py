"""Recompute 现状行为的锁定测试（改造前基线，不许改）。"""

import unittest

from dsulib.union import Recompute


class TestAdd(unittest.TestCase):
    def test_add_creates_singleton(self):
        d = Recompute()
        d.add("a")
        self.assertEqual(d.component_size("a"), 1)
        self.assertEqual(d.members("a"), {"a"})
        self.assertEqual(d.count_components(), 1)

    def test_add_is_rejected_for_existing(self):
        d = Recompute()
        d.add("a")
        with self.assertRaises(ValueError):
            d.add("a")

    def test_add_none_raises(self):
        d = Recompute()
        with self.assertRaises(ValueError):
            d.add(None)


class TestUnion(unittest.TestCase):
    def test_union_merges_two_singletons(self):
        d = Recompute()
        d.add("a")
        d.add("b")
        size = d.union("a", "b")
        self.assertEqual(size, 2)
        self.assertTrue(d.connected("a", "b"))
        self.assertEqual(d.count_components(), 1)

    def test_union_self_is_idempotent(self):
        d = Recompute()
        d.add("a")
        d.add("b")
        d.union("a", "b")
        self.assertEqual(d.union("a", "a"), 2)
        self.assertEqual(d.union("a", "b"), 2)
        self.assertTrue(d.connected("a", "b"))
        self.assertEqual(d.count_components(), 1)

    def test_union_is_transitive(self):
        d = Recompute()
        for x in ["a", "b", "c", "d"]:
            d.add(x)
        d.union("a", "b")
        d.union("c", "d")
        self.assertFalse(d.connected("a", "c"))
        d.union("b", "c")
        self.assertTrue(d.connected("a", "d"))
        self.assertEqual(d.component_size("a"), 4)
        self.assertEqual(d.count_components(), 1)

    def test_union_unknown_element_raises(self):
        d = Recompute()
        d.add("a")
        with self.assertRaises(ValueError):
            d.union("a", "ghost")
        with self.assertRaises(ValueError):
            d.union("ghost", "a")


class TestQueries(unittest.TestCase):
    def test_connected_unknown_raises(self):
        d = Recompute()
        d.add("a")
        with self.assertRaises(ValueError):
            d.connected("a", "ghost")

    def test_component_size_unknown_raises(self):
        d = Recompute()
        d.add("a")
        with self.assertRaises(ValueError):
            d.component_size("ghost")

    def test_members_unknown_raises(self):
        d = Recompute()
        d.add("a")
        with self.assertRaises(ValueError):
            d.members("ghost")

    def test_members_returns_a_copy(self):
        d = Recompute()
        d.add("a")
        d.add("b")
        d.union("a", "b")
        snapshot = d.members("a")
        snapshot.add("intruder")
        self.assertEqual(d.members("a"), {"a", "b"})
        self.assertEqual(d.component_size("a"), 2)

    def test_count_on_empty_structure(self):
        d = Recompute()
        self.assertEqual(d.count_components(), 0)

    def test_count_after_merges(self):
        d = Recompute()
        for x in range(6):
            d.add(x)
        d.union(0, 1)
        d.union(2, 3)
        d.union(3, 4)
        self.assertEqual(d.count_components(), 3)
        self.assertEqual(sorted(d.members(3)), [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
