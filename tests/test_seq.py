"""Baseline behaviour tests for MutList.

This file pins the current in-place mutable semantics. It must stay
unchanged and keep passing as the library evolves.
"""

import unittest

from persistx import MutList


class MutListBuildTest(unittest.TestCase):
    def test_empty_initial(self):
        m = MutList()
        self.assertEqual(len(m), 0)
        self.assertEqual(m.snapshot(), [])

    def test_initial_value(self):
        m = MutList([1, 2, 3])
        self.assertEqual(len(m), 3)
        self.assertEqual(m.snapshot(), [1, 2, 3])

    def test_initial_is_copied(self):
        src = [1, 2, 3]
        m = MutList(src)
        m.push(4)
        self.assertEqual(src, [1, 2, 3])
        self.assertEqual(m.snapshot(), [1, 2, 3, 4])


class MutListPushPopTest(unittest.TestCase):
    def test_push_returns_self(self):
        m = MutList()
        self.assertIs(m.push(1), m)

    def test_push_appends_at_tail(self):
        m = MutList([1])
        m.push(2).push(3)
        self.assertEqual(m.snapshot(), [1, 2, 3])

    def test_pop_returns_tail(self):
        m = MutList([1, 2, 3])
        self.assertEqual(m.pop(), 3)
        self.assertEqual(m.snapshot(), [1, 2])

    def test_pop_empty_raises(self):
        m = MutList()
        with self.assertRaises(IndexError):
            m.pop()


class MutListGetSetTest(unittest.TestCase):
    def test_get_in_range(self):
        m = MutList([10, 20, 30])
        self.assertEqual(m.get(0), 10)
        self.assertEqual(m.get(2), 30)

    def test_set_in_range(self):
        m = MutList([10, 20, 30])
        self.assertIs(m.set(1, 99), m)
        self.assertEqual(m.snapshot(), [10, 99, 30])

    def test_get_out_of_range(self):
        m = MutList([1, 2])
        with self.assertRaises(IndexError):
            m.get(2)
        with self.assertRaises(IndexError):
            m.get(-1)

    def test_set_out_of_range(self):
        m = MutList([1, 2])
        with self.assertRaises(IndexError):
            m.set(2, 0)
        with self.assertRaises(IndexError):
            m.set(-1, 0)


class MutListSnapshotTest(unittest.TestCase):
    def test_snapshot_is_shallow_copy(self):
        m = MutList([1, 2])
        snap = m.snapshot()
        m.push(3)
        self.assertEqual(snap, [1, 2])
        self.assertEqual(m.snapshot(), [1, 2, 3])

    def test_snapshot_two_are_distinct_objects(self):
        m = MutList([1])
        a = m.snapshot()
        b = m.snapshot()
        self.assertIsNot(a, b)

    def test_len_tracks_mutation(self):
        m = MutList()
        m.push(1)
        m.push(2)
        self.assertEqual(len(m), 2)
        m.pop()
        self.assertEqual(len(m), 1)


if __name__ == "__main__":
    unittest.main()
