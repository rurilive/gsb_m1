"""NaiveSet 现有行为的锁定测试，改造后仍须全绿。"""

import unittest

from cuckoof import NaiveSet
from cuckoof.naive import NaiveSet as NaiveSetDirect


class TestNaiveSet(unittest.TestCase):
    def test_add_new_and_duplicate(self):
        s = NaiveSet(capacity=16)
        self.assertTrue(s.add("a"))
        self.assertFalse(s.add("a"))
        self.assertEqual(len(s), 1)

    def test_contains_exact(self):
        s = NaiveSet(capacity=16)
        for i in range(20):
            s.add("k%d" % i)
        for i in range(20):
            self.assertIn("k%d" % i, s)
        self.assertNotIn("missing", s)
        self.assertFalse(s.contains("missing"))

    def test_contains_method_matches_in(self):
        s = NaiveSet(capacity=8)
        s.add("x")
        self.assertEqual(s.contains("x"), "x" in s)

    def test_remove_true_then_false(self):
        s = NaiveSet(capacity=8)
        s.add("x")
        self.assertTrue(s.remove("x"))
        self.assertFalse(s.remove("x"))

    def test_remove_missing_does_not_change(self):
        s = NaiveSet(capacity=8)
        s.add("a")
        s.add("b")
        self.assertFalse(s.remove("c"))
        self.assertEqual(len(s), 2)
        self.assertIn("a", s)
        self.assertIn("b", s)

    def test_removed_key_not_contained(self):
        s = NaiveSet(capacity=8)
        for i in range(5):
            s.add("r%d" % i)
        s.remove("r2")
        self.assertNotIn("r2", s)
        self.assertIn("r3", s)

    def test_len_counts_members(self):
        s = NaiveSet(capacity=8)
        s.add("a")
        s.add("a")
        s.add("b")
        self.assertEqual(len(s), 2)

    def test_stats_is_fresh_dict(self):
        s = NaiveSet(capacity=8)
        snap = s.stats()
        snap["size"] = 99
        self.assertEqual(s.stats()["size"], 0)
        self.assertEqual(s.stats()["capacity"], 8)

    def test_bad_capacity_rejected(self):
        with self.assertRaises(ValueError):
            NaiveSet(capacity=0)
        with self.assertRaises(ValueError):
            NaiveSet(capacity=-3)

    def test_no_false_positive(self):
        s = NaiveSet(capacity=64)
        for i in range(32):
            s.add("in-%d" % i)
        for i in range(200):
            self.assertNotIn("out-%d" % i, s)

    def test_exported_name_is_same_class(self):
        self.assertIs(NaiveSet, NaiveSetDirect)


if __name__ == "__main__":
    unittest.main()