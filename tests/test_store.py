"""RateStore 现有朴素行为的锁定测试。

这份基线在改造前后都必须全绿，一个字都不许改动。
"""

import unittest

from ratestore.store import DEFAULT_LABEL, RateStore, RateStoreError


class TestRateStoreBaseline(unittest.TestCase):
    def test_new_store_is_empty(self):
        s = RateStore()
        self.assertEqual(s.labels(), [])
        self.assertEqual(s.count(), 0)
        self.assertEqual(s.sum(), 0.0)
        self.assertEqual(s.mean(), 0.0)

    def test_default_label_constant(self):
        self.assertEqual(DEFAULT_LABEL, "default")

    def test_record_accumulates_count_and_sum(self):
        s = RateStore()
        s.record(10)
        s.record(20)
        s.record(30)
        self.assertEqual(s.count(), 3)
        self.assertEqual(s.sum(), 60.0)
        self.assertEqual(s.mean(), 20.0)

    def test_count_sum_mean_take_label(self):
        s = RateStore()
        s.record(1.0, label="a")
        s.record(3.0, label="a")
        s.record(100.0, label="b")
        self.assertEqual(s.count("a"), 2)
        self.assertEqual(s.sum("a"), 4.0)
        self.assertEqual(s.mean("a"), 2.0)
        self.assertEqual(s.count("b"), 1)
        self.assertEqual(s.sum("b"), 100.0)

    def test_labels_are_isolated(self):
        s = RateStore()
        s.record(5, label="x")
        s.record(7, label="y")
        self.assertEqual(s.count("x"), 1)
        self.assertEqual(s.count("y"), 1)
        self.assertEqual(s.sum("x"), 5.0)
        self.assertEqual(s.sum("y"), 7.0)

    def test_unknown_label_reads_zero(self):
        s = RateStore()
        self.assertEqual(s.count("ghost"), 0)
        self.assertEqual(s.sum("ghost"), 0.0)
        self.assertEqual(s.mean("ghost"), 0.0)

    def test_mean_of_empty_is_zero(self):
        s = RateStore()
        self.assertEqual(s.mean("nope"), 0.0)

    def test_labels_sorted_and_deduped(self):
        s = RateStore()
        s.record(1, label="c")
        s.record(2, label="a")
        s.record(3, label="a")
        s.record(4, label="b")
        self.assertEqual(s.labels(), ["a", "b", "c"])

    def test_default_label_participates_in_labels(self):
        s = RateStore()
        s.record(1)
        s.record(2, label="z")
        self.assertEqual(s.labels(), ["default", "z"])

    def test_record_returns_self(self):
        s = RateStore()
        self.assertIs(s.record(1), s)

    def test_count_unchanged_by_reads(self):
        s = RateStore()
        s.record(1)
        s.record(2)
        s.count()
        s.sum()
        s.mean()
        self.assertEqual(s.count(), 2)
        self.assertEqual(s.sum(), 3.0)

    def test_negative_values(self):
        s = RateStore()
        s.record(-4)
        s.record(2)
        self.assertEqual(s.count(), 2)
        self.assertEqual(s.sum(), -2.0)
        self.assertEqual(s.mean(), -1.0)

    def test_integer_values_coerced_to_float(self):
        s = RateStore()
        s.record(3)
        self.assertIsInstance(s.sum(), float)
        self.assertEqual(s.sum(), 3.0)

    def test_labels_returns_fresh_list(self):
        s = RateStore()
        s.record(1, label="a")
        out = s.labels()
        out.append("junk")
        self.assertEqual(s.labels(), ["a"])

    def test_merge_adds_counts_and_sums(self):
        a = RateStore()
        a.record(1, label="x")
        a.record(2, label="x")
        b = RateStore()
        b.record(3, label="x")
        b.record(10, label="y")
        a.merge(b)
        self.assertEqual(a.count("x"), 3)
        self.assertEqual(a.sum("x"), 6.0)
        self.assertEqual(a.count("y"), 1)
        self.assertEqual(a.sum("y"), 10.0)
        self.assertEqual(a.labels(), ["x", "y"])

    def test_merge_returns_self(self):
        a = RateStore()
        b = RateStore()
        self.assertIs(a.merge(b), a)

    def test_merge_is_idempotent_when_other_empty(self):
        a = RateStore()
        a.record(4)
        a.merge(RateStore())
        self.assertEqual(a.count(), 1)
        self.assertEqual(a.sum(), 4.0)

    def test_merge_rejects_non_store(self):
        a = RateStore()
        with self.assertRaises(RateStoreError):
            a.merge(object())

    def test_error_is_value_error(self):
        self.assertTrue(issubclass(RateStoreError, ValueError))

    def test_many_records_accumulate_exactly(self):
        s = RateStore()
        for i in range(1000):
            s.record(i, label="bulk")
        self.assertEqual(s.count("bulk"), 1000)
        self.assertEqual(s.sum("bulk"), 999 * 1000 / 2)


if __name__ == "__main__":
    unittest.main()
