"""Ledger 现有行为的锁定测试。"""

import unittest

from dedupkit.ledger import Ledger


class TestLedger(unittest.TestCase):
    def test_add_creates_shard_on_demand(self):
        ledger = Ledger()
        self.assertEqual(ledger.names(), ())
        self.assertTrue(ledger.add("a", "u1"))
        self.assertEqual(ledger.names(), ("a",))
        self.assertFalse(ledger.add("a", "u1"))
        self.assertTrue(ledger.add("a", "u2"))

    def test_count_is_per_shard(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        ledger.add("a", "u2")
        ledger.add("b", "u2")
        self.assertEqual(ledger.count("a"), 2)
        self.assertEqual(ledger.count("b"), 1)

    def test_count_of_unknown_shard_raises_keyerror(self):
        ledger = Ledger()
        with self.assertRaises(KeyError):
            ledger.count("nope")

    def test_keys_of_unknown_shard_raises_keyerror(self):
        ledger = Ledger()
        with self.assertRaises(KeyError):
            ledger.keys("nope")

    def test_total_of_empty_ledger_is_zero(self):
        self.assertEqual(Ledger().total(), 0)

    def test_total_sums_disjoint_shards(self):
        ledger = Ledger()
        for key in ["u1", "u2", "u3"]:
            ledger.add("a", key)
        ledger.add("b", "u4")
        self.assertEqual(ledger.total(), 4)

    def test_total_counts_cross_shard_duplicates_once_per_shard(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        ledger.add("b", "u1")
        # u1 两片各出现一次，total() 把它记了两次
        self.assertEqual(ledger.total(), 2)

    def test_names_are_sorted(self):
        ledger = Ledger()
        for name in ["z", "a", "m"]:
            ledger.add(name, "u1")
        self.assertEqual(ledger.names(), ("a", "m", "z"))

    def test_keys_returns_snapshot(self):
        ledger = Ledger()
        ledger.add("a", "u1")
        snapshot = ledger.keys("a")
        ledger.add("a", "u2")
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(set(ledger.keys("a")), {"u1", "u2"})

    def test_non_string_shard_name_raises_typeerror(self):
        ledger = Ledger()
        with self.assertRaises(TypeError):
            ledger.add(1, "u1")


if __name__ == "__main__":
    unittest.main()
