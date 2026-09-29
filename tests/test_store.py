"""KeyValueStore 现有行为的锁定测试。

只覆盖改造前已经具备的逐键读写能力：put 覆盖、get 取当前值、delete、
keys 与 __contains__。新增能力（跨键事务、一致性快照、写时复制、
快照回收）另开测试文件，不改动本文件。
"""

import unittest

from snapstore.kv import KeyValueStore


class TestPutAndGet(unittest.TestCase):
    def test_put_then_get(self):
        store = KeyValueStore()
        store.put("a", 1)
        self.assertEqual(store.get("a"), 1)

    def test_put_overwrites(self):
        store = KeyValueStore()
        store.put("a", 1)
        store.put("a", 2)
        self.assertEqual(store.get("a"), 2)

    def test_get_missing_key_is_none(self):
        store = KeyValueStore()
        self.assertIsNone(store.get("nope"))

    def test_value_object_is_same_instance(self):
        store = KeyValueStore()
        obj = {"n": 1}
        store.put("a", obj)
        self.assertIs(store.get("a"), obj)

    def test_value_none_is_kept_distinct_from_missing(self):
        store = KeyValueStore()
        store.put("a", None)
        self.assertIn("a", store)
        self.assertIsNone(store.get("a"))


class TestDelete(unittest.TestCase):
    def test_delete_returns_whether_existed(self):
        store = KeyValueStore()
        store.put("a", 1)
        self.assertTrue(store.delete("a"))
        self.assertFalse(store.delete("a"))

    def test_get_after_delete_is_none(self):
        store = KeyValueStore()
        store.put("a", 1)
        store.delete("a")
        self.assertIsNone(store.get("a"))

    def test_rewrite_after_delete(self):
        store = KeyValueStore()
        store.put("a", 1)
        store.delete("a")
        store.put("a", 9)
        self.assertEqual(store.get("a"), 9)


class TestKeys(unittest.TestCase):
    def test_keys_are_sorted_and_live(self):
        store = KeyValueStore()
        store.put("b", 1)
        store.put("a", 1)
        store.put("c", 1)
        store.delete("a")
        self.assertEqual(store.keys(), ["b", "c"])

    def test_empty_store(self):
        store = KeyValueStore()
        self.assertEqual(store.keys(), [])
        self.assertEqual(store.get("anything"), None)

    def test_contains(self):
        store = KeyValueStore()
        store.put("a", 1)
        self.assertIn("a", store)
        self.assertNotIn("b", store)
        store.delete("a")
        self.assertNotIn("a", store)


class TestIndependentKeys(unittest.TestCase):
    def test_writes_are_per_key_independent(self):
        store = KeyValueStore()
        store.put("a", 1)
        store.put("b", 2)
        store.put("a", 10)
        self.assertEqual(store.get("a"), 10)
        self.assertEqual(store.get("b"), 2)

    def test_delete_one_key_leaves_others(self):
        store = KeyValueStore()
        store.put("a", 1)
        store.put("b", 2)
        store.delete("a")
        self.assertEqual(store.keys(), ["b"])
        self.assertEqual(store.get("b"), 2)


if __name__ == "__main__":
    unittest.main()