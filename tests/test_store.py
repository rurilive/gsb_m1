"""LimitedDict 现有行为的锁定测试。

只覆盖当前实现已经具备的能力：读写、容量满时的删除、删除与遍历、
非法容量的构造期拒绝。新增行为（过期、LRU 淘汰、惰性清理、注入时钟）
另建测试文件，不改动本文件。
"""

import unittest

from expirex.store import LimitedDict


class TestGetAndSet(unittest.TestCase):
    def test_get_missing_returns_none(self):
        d = LimitedDict(2)
        self.assertIsNone(d.get("absent"))

    def test_set_then_get(self):
        d = LimitedDict(2)
        d.set("a", 1)
        self.assertEqual(d.get("a"), 1)

    def test_set_existing_key_updates_value(self):
        d = LimitedDict(2)
        d.set("a", 1)
        d.set("a", 2)
        self.assertEqual(d.get("a"), 2)
        self.assertEqual(len(d), 1)

    def test_contains_and_len_and_keys(self):
        d = LimitedDict(3)
        d.set("a", 1)
        d.set("b", 2)
        self.assertIn("a", d)
        self.assertNotIn("z", d)
        self.assertEqual(len(d), 2)
        self.assertEqual(d.keys(), ["a", "b"])


class TestDelete(unittest.TestCase):
    def test_delete_removes_key(self):
        d = LimitedDict(2)
        d.set("a", 1)
        d.set("b", 2)
        d.delete("a")
        self.assertIsNone(d.get("a"))
        self.assertEqual(len(d), 1)

    def test_delete_missing_is_noop(self):
        d = LimitedDict(2)
        d.set("a", 1)
        d.delete("absent")
        self.assertEqual(len(d), 1)


class TestCapacityEviction(unittest.TestCase):
    def test_evicts_one_when_full(self):
        d = LimitedDict(2)
        d.set("a", 1)
        d.set("b", 2)
        d.set("c", 3)
        self.assertEqual(len(d), 2)
        self.assertEqual(d.get("c"), 3)

    def test_evicts_a_preexisting_key_on_overflow(self):
        d = LimitedDict(1)
        d.set("a", 1)
        d.set("b", 2)
        self.assertEqual(len(d), 1)
        self.assertEqual(d.get("b"), 2)
        self.assertIsNone(d.get("a"))

    def test_update_does_not_evict(self):
        d = LimitedDict(2)
        d.set("a", 1)
        d.set("b", 2)
        d.set("b", 3)
        self.assertEqual(len(d), 2)
        self.assertEqual(d.get("b"), 3)


class TestCapacityGuard(unittest.TestCase):
    def test_zero_capacity_rejected(self):
        with self.assertRaises(ValueError):
            LimitedDict(0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(ValueError):
            LimitedDict(-3)


if __name__ == "__main__":
    unittest.main()
