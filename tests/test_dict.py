"""KVStore 现有行为的锁定测试。

只覆盖当前字典式实现已经具备的能力：put 覆盖、get 取值、delete 抹键、
keys 与 items 的顺序、len 与 in。新增能力（内存表落段、段上读取、墓碑、
合并、范围扫描、副本统计）另开测试文件，本文件一字不改。
"""

import unittest

from logstore.store import KVStore


class TestPutAndGet(unittest.TestCase):
    def test_put_new_key_returns_false(self):
        store = KVStore()
        self.assertFalse(store.put("a", 1))

    def test_put_existing_key_returns_true(self):
        store = KVStore()
        store.put("a", 1)
        self.assertTrue(store.put("a", 2))

    def test_get_returns_latest_value(self):
        store = KVStore()
        store.put("a", 1)
        store.put("a", 2)
        self.assertEqual(store.get("a"), 2)

    def test_get_missing_key_is_none(self):
        store = KVStore()
        self.assertIsNone(store.get("missing"))

    def test_get_missing_key_returns_default(self):
        store = KVStore()
        self.assertEqual(store.get("missing", 0), 0)

    def test_value_object_is_same_instance(self):
        store = KVStore()
        obj = {"n": 1}
        store.put("a", obj)
        self.assertIs(store.get("a"), obj)


class TestDelete(unittest.TestCase):
    def test_delete_returns_whether_existed(self):
        store = KVStore()
        store.put("a", 1)
        self.assertTrue(store.delete("a"))
        self.assertFalse(store.delete("a"))

    def test_get_after_delete_is_none(self):
        store = KVStore()
        store.put("a", 1)
        store.delete("a")
        self.assertIsNone(store.get("a"))

    def test_delete_then_put_stores_new_value(self):
        store = KVStore()
        store.put("a", 1)
        store.delete("a")
        self.assertFalse(store.put("a", 9))
        self.assertEqual(store.get("a"), 9)


class TestOrderingAndMembership(unittest.TestCase):
    def test_keys_are_sorted(self):
        store = KVStore()
        for k in ("c", "a", "b"):
            store.put(k, k)
        self.assertEqual(store.keys(), ["a", "b", "c"])

    def test_items_are_sorted_pairs(self):
        store = KVStore()
        store.put("b", 2)
        store.put("a", 1)
        self.assertEqual(store.items(), [("a", 1), ("b", 2)])

    def test_len_and_contains(self):
        store = KVStore()
        self.assertEqual(len(store), 0)
        store.put("a", 1)
        store.put("b", 2)
        self.assertEqual(len(store), 2)
        self.assertIn("a", store)
        self.assertNotIn("z", store)
        store.delete("a")
        self.assertEqual(len(store), 1)
        self.assertNotIn("a", store)


if __name__ == "__main__":
    unittest.main()