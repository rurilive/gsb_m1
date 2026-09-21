"""GCounter 现有行为的锁定测试。"""

import unittest

from crdtbox.counter import GCounter


class TestGCounter(unittest.TestCase):
    def test_incr_accumulates_same_slot(self):
        c = GCounter("a")
        c.incr("a", 3)
        c.incr("a", 2)
        self.assertEqual(c.value(), 5)

    def test_incr_defaults_to_one(self):
        c = GCounter("a")
        c.incr("a")
        self.assertEqual(c.value(), 1)

    def test_value_sums_slots(self):
        c = GCounter("a")
        c.incr("a", 2)
        c.incr("b", 3)
        self.assertEqual(c.value(), 5)

    def test_fresh_counter_is_zero(self):
        self.assertEqual(GCounter("a").value(), 0)

    def test_merge_unions_disjoint_slots(self):
        a = GCounter("a")
        b = GCounter("b")
        a.incr("a", 3)
        b.incr("b", 4)
        a.merge(b)
        self.assertEqual(a.value(), 7)

    def test_merge_takes_max_for_same_slot(self):
        a = GCounter("a")
        b = GCounter("a")
        a.incr("a", 3)
        b.incr("a", 5)
        a.merge(b)
        self.assertEqual(a.value(), 5)

    def test_merge_is_idempotent(self):
        a = GCounter("a")
        b = GCounter("b")
        a.incr("a", 3)
        b.incr("b", 4)
        a.merge(b)
        a.merge(b)
        self.assertEqual(a.value(), 7)

    def test_merge_returns_self(self):
        a = GCounter("a")
        self.assertIs(a.merge(GCounter("b")), a)

    def test_merge_rejects_other_types(self):
        with self.assertRaises(TypeError):
            GCounter("a").merge({"a": 1})

    def test_incr_rejects_non_positive(self):
        c = GCounter("a")
        with self.assertRaises(ValueError):
            c.incr("a", 0)
        with self.assertRaises(ValueError):
            c.incr("a", -1)

    def test_replica_id_must_be_non_empty_string(self):
        with self.assertRaises(ValueError):
            GCounter("")
        with self.assertRaises(ValueError):
            GCounter(None)

    def test_replica_id_is_public(self):
        self.assertEqual(GCounter("node-1").replica_id, "node-1")


if __name__ == "__main__":
    unittest.main()
