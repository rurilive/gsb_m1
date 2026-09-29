"""朴素精确计数字典的锁定测试。

只覆盖当前实现已经具备的能力：加入与累加、精确计数、合计、键枚举、
逐键精确合并、重置、参数与键的校验。新增能力（计数器数组、哈希定位、
最小值估算、单侧误差与误差界、点查询与频繁项、可交换可结合可幂等的
草图合并、减除与区间查询、边界校验）另开测试文件，本文件一字不改。
"""

import unittest

from sketchly.counter import ExactCounter


class TestAddAndValue(unittest.TestCase):
    def test_empty_value_is_zero(self):
        self.assertEqual(ExactCounter().value("nope"), 0)

    def test_add_increases_value(self):
        counter = ExactCounter()
        counter.add("a")
        self.assertEqual(counter.value("a"), 1)

    def test_add_accumulates(self):
        counter = ExactCounter()
        counter.add("a")
        counter.add("a", 4)
        self.assertEqual(counter.value("a"), 5)

    def test_add_many_counts_each(self):
        counter = ExactCounter()
        counter.add_many(["a", "b", "a", "c", "b", "a"])
        self.assertEqual(counter.value("a"), 3)
        self.assertEqual(counter.value("b"), 2)
        self.assertEqual(counter.value("c"), 1)

    def test_total_sums_all_counts(self):
        counter = ExactCounter()
        counter.add_many(["a", "b", "a", "c", "b", "a"])
        self.assertEqual(counter.total(), 6)


class TestKeys(unittest.TestCase):
    def test_keys_lists_seen_keys(self):
        counter = ExactCounter()
        counter.add_many(["a", "b", "a"])
        self.assertEqual(sorted(counter.keys()), ["a", "b"])

    def test_empty_counter_has_no_keys(self):
        self.assertEqual(ExactCounter().keys(), [])


class TestValidation(unittest.TestCase):
    def test_add_rejects_empty_key(self):
        with self.assertRaises(ValueError):
            ExactCounter().add("")

    def test_add_rejects_non_str_key(self):
        with self.assertRaises(ValueError):
            ExactCounter().add(123)

    def test_add_rejects_none(self):
        with self.assertRaises(ValueError):
            ExactCounter().add(None)

    def test_add_rejects_negative_amount(self):
        with self.assertRaises(ValueError):
            ExactCounter().add("a", -1)

    def test_add_rejects_non_int_amount(self):
        with self.assertRaises(ValueError):
            ExactCounter().add("a", 1.5)

    def test_add_rejects_bool_amount(self):
        with self.assertRaises(ValueError):
            ExactCounter().add("a", True)


class TestMerge(unittest.TestCase):
    def test_merge_accumulates_per_key(self):
        left = ExactCounter()
        left.add_many(["a", "b"])
        right = ExactCounter()
        right.add_many(["b", "c", "c"])
        left.merge(right)
        self.assertEqual(left.value("a"), 1)
        self.assertEqual(left.value("b"), 2)
        self.assertEqual(left.value("c"), 2)

    def test_merge_is_exact_and_commutative(self):
        left = ExactCounter()
        left.add_many(["a", "a", "b"])
        right = ExactCounter()
        right.add_many(["b", "c"])
        other = ExactCounter()
        other.add_many(["a", "a", "b"])
        other.merge(right)
        left.merge(right)
        self.assertEqual(left.value("a"), other.value("a"))
        self.assertEqual(left.value("b"), other.value("b"))
        self.assertEqual(left.value("c"), other.value("c"))

    def test_merge_rejects_non_counter(self):
        with self.assertRaises(ValueError):
            ExactCounter().merge({"a": 1})


class TestReset(unittest.TestCase):
    def test_reset_clears_everything(self):
        counter = ExactCounter()
        counter.add_many(["a", "b"])
        counter.reset()
        self.assertEqual(counter.value("a"), 0)
        self.assertEqual(counter.total(), 0)
        self.assertEqual(counter.keys(), [])


if __name__ == "__main__":
    unittest.main()
