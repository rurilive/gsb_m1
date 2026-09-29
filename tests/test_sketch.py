"""ExactCounter 的基线测试。

这些用例锁住改造前的精确行为，是后读的兼容性契约，一字不可改。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sketchlib import ExactCounter, SketchError


class ExactCounterBaselineTest(unittest.TestCase):
    def setUp(self):
        self.counter = ExactCounter()

    # ---- add / count ----

    def test_new_counter_is_empty(self):
        self.assertEqual(self.counter.count("missing"), 0)
        self.assertEqual(self.counter.total(), 0)
        self.assertEqual(self.counter.distinct(), 0)
        self.assertEqual(len(self.counter), 0)

    def test_add_default_increment_is_one(self):
        self.counter.add("a")
        self.assertEqual(self.counter.count("a"), 1)
        self.counter.add("a")
        self.assertEqual(self.counter.count("a"), 2)

    def test_add_returns_new_count(self):
        self.assertEqual(self.counter.add("a"), 1)
        self.assertEqual(self.counter.add("a"), 2)
        self.assertEqual(self.counter.add("b"), 1)
        self.assertEqual(self.counter.add("a", 5), 7)

    def test_add_with_explicit_increment(self):
        self.counter.add("a", 4)
        self.counter.add("b", 3)
        self.assertEqual(self.counter.count("a"), 4)
        self.assertEqual(self.counter.count("b"), 3)

    def test_add_zero_increment_is_allowed_and_noop(self):
        self.counter.add("a", 0)
        self.assertEqual(self.counter.count("a"), 0)
        self.assertIn("a", self.counter)

    def test_count_is_exact(self):
        for i in range(10):
            self.counter.add("k", i + 1)
        self.assertEqual(self.counter.count("k"), 55)

    # ---- total / distinct ----

    def test_total_sums_all_counts(self):
        self.counter.add("a", 2)
        self.counter.add("b", 3)
        self.counter.add("c")
        self.assertEqual(self.counter.total(), 6)

    def test_distinct_counts_keys(self):
        for key in ("a", "b", "a", "c", "b", "a"):
            self.counter.add(key)
        self.assertEqual(self.counter.distinct(), 3)
        self.assertEqual(self.counter.total(), 6)

    def test_contains_reflects_seen_keys(self):
        self.counter.add("seen")
        self.assertIn("seen", self.counter)
        self.assertNotIn("unseen", self.counter)

    # ---- top ----

    def test_top_orders_by_count_descending(self):
        self.counter.add("a", 3)
        self.counter.add("b", 5)
        self.counter.add("c", 1)
        self.assertEqual(self.counter.top(3), [("b", 5), ("a", 3), ("c", 1)])

    def test_top_truncates_to_k(self):
        self.counter.add("a", 3)
        self.counter.add("b", 5)
        self.counter.add("c", 1)
        self.assertEqual(self.counter.top(1), [("b", 5)])
        self.assertEqual(self.counter.top(2), [("b", 5), ("a", 3)])

    def test_top_ties_break_by_insertion_order(self):
        # 三个键计数都是 1，插入序 c 早于 a 早于 b。
        self.counter.add("c")
        self.counter.add("a")
        self.counter.add("b")
        self.assertEqual(self.counter.top(3), [("c", 1), ("a", 1), ("b", 1)])

    def test_top_k_larger_than_data(self):
        self.counter.add("a")
        self.counter.add("b")
        self.assertEqual(self.counter.top(10), [("a", 1), ("b", 1)])

    def test_top_zero_or_negative_is_empty(self):
        self.counter.add("a")
        self.assertEqual(self.counter.top(0), [])
        self.assertEqual(self.counter.top(-3), [])

    # ---- 异常 ----

    def test_add_none_key_raises(self):
        with self.assertRaises(SketchError):
            self.counter.add(None)

    def test_add_negative_increment_raises(self):
        with self.assertRaises(SketchError):
            self.counter.add("a", -1)
        self.assertEqual(self.counter.count("a"), 0)

    def test_add_non_integer_increment_raises(self):
        with self.assertRaises(SketchError):
            self.counter.add("a", 1.5)

    def test_sketch_error_is_exception_subclass(self):
        self.assertTrue(issubclass(SketchError, Exception))
        with self.assertRaises(SketchError):
            self.counter.add(None)

    # ---- 精确性 ----

    def test_counts_stay_exact(self):
        data = ["x"] * 7 + ["y"] * 3 + ["z"] * 11
        for key in data:
            self.counter.add(key)
        self.assertEqual(self.counter.count("x"), 7)
        self.assertEqual(self.counter.count("y"), 3)
        self.assertEqual(self.counter.count("z"), 11)
        self.assertEqual(self.counter.total(), len(data))


if __name__ == "__main__":
    unittest.main()
