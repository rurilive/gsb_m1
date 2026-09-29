"""基础集合现有行为的锁定测试。

只覆盖当前实现已具备的能力：add 加入、remove 删除、contains 判断、
元素集合副本独立、构造与类型校验。
"""

import unittest

from orset.set import ORSet, SetError


class TestORSetBasics(unittest.TestCase):
    def test_starts_empty(self):
        s = ORSet()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.elements(), set())

    def test_construct_with_elements(self):
        s = ORSet(elements=["a", "b"])
        self.assertTrue(s.contains("a"))
        self.assertTrue(s.contains("b"))
        self.assertEqual(len(s), 2)

    def test_add_returns_self_and_contains(self):
        s = ORSet()
        self.assertIs(s.add("x"), s)
        self.assertTrue(s.contains("x"))

    def test_add_same_element_twice_is_idempotent(self):
        s = ORSet()
        s.add("x").add("x")
        self.assertEqual(len(s), 1)

    def test_remove_returns_self(self):
        s = ORSet(elements=["x"])
        self.assertIs(s.remove("x"), s)
        self.assertFalse(s.contains("x"))

    def test_remove_missing_is_noop(self):
        s = ORSet(elements=["x"])
        s.remove("y")
        self.assertTrue(s.contains("x"))
        self.assertEqual(len(s), 1)

    def test_contains_missing_is_false(self):
        s = ORSet()
        self.assertFalse(s.contains("nope"))

    def test_elements_returns_independent_copy(self):
        s = ORSet(elements=["x"])
        snap = s.elements()
        snap.add("y")
        self.assertFalse(s.contains("y"))

    def test_iteration_yields_elements(self):
        s = ORSet(elements=["a", "b"])
        self.assertEqual(set(iter(s)), {"a", "b"})

    def test_repr_lists_sorted_elements(self):
        s = ORSet(elements=["b", "a"])
        self.assertEqual(repr(s), "ORSet(['a', 'b'])")


class TestORSetValidation(unittest.TestCase):
    def test_add_rejects_non_string(self):
        s = ORSet()
        with self.assertRaises(SetError):
            s.add(1)

    def test_remove_rejects_non_string(self):
        s = ORSet()
        with self.assertRaises(SetError):
            s.remove(None)

    def test_contains_non_string_is_false(self):
        s = ORSet(elements=["x"])
        self.assertFalse(s.contains(5))


if __name__ == "__main__":
    unittest.main()