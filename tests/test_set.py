"""TwoPhaseSet 现有行为的锁定测试。"""

import unittest

from crdtbox.set import TwoPhaseSet


class TestTwoPhaseSet(unittest.TestCase):
    def test_add_then_contains(self):
        s = TwoPhaseSet()
        s.add("red")
        self.assertTrue(s.contains("red"))
        self.assertFalse(s.contains("blue"))

    def test_add_is_chainable(self):
        s = TwoPhaseSet()
        s.add("red").add("blue")
        self.assertEqual(s.value(), ("blue", "red"))

    def test_value_is_sorted_tuple(self):
        s = TwoPhaseSet()
        for item in ("c", "a", "b"):
            s.add(item)
        self.assertEqual(s.value(), ("a", "b", "c"))

    def test_value_is_empty_for_fresh_set(self):
        self.assertEqual(TwoPhaseSet().value(), ())

    def test_discard_removes_element(self):
        s = TwoPhaseSet()
        s.add("red")
        s.discard("red")
        self.assertFalse(s.contains("red"))
        self.assertEqual(s.value(), ())

    def test_discard_absent_element_is_harmless(self):
        s = TwoPhaseSet()
        s.discard("ghost")
        self.assertFalse(s.contains("ghost"))
        self.assertEqual(s.value(), ())

    def test_discard_returns_self(self):
        s = TwoPhaseSet()
        self.assertIs(s.discard("red"), s)

    def test_merge_unions_disjoint_adds(self):
        a = TwoPhaseSet()
        b = TwoPhaseSet()
        a.add("red")
        b.add("blue")
        a.merge(b)
        self.assertEqual(a.value(), ("blue", "red"))

    def test_merge_carries_removals_from_both_sides(self):
        a = TwoPhaseSet()
        b = TwoPhaseSet()
        a.add("red")
        b.merge(a)          # b 先看到 red
        b.discard("red")
        a.merge(b)
        self.assertFalse(a.contains("red"))
        self.assertEqual(a.value(), ())

    def test_merge_is_idempotent(self):
        a = TwoPhaseSet()
        b = TwoPhaseSet()
        a.add("red")
        b.add("blue")
        a.merge(b)
        a.merge(b)
        self.assertEqual(a.value(), ("blue", "red"))

    def test_merge_returns_self(self):
        a = TwoPhaseSet()
        self.assertIs(a.merge(TwoPhaseSet()), a)

    def test_merge_rejects_other_types(self):
        with self.assertRaises(TypeError):
            TwoPhaseSet().merge({"red"})


if __name__ == "__main__":
    unittest.main()
