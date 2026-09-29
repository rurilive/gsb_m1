"""SortedMap 现有行为的锁定基线。

这份测试锁住改造前的朴素有序数组语义，跳表改造之后必须一字不改且仍然全绿。
"""

import unittest

from skippy.sortedmap import SortedMap


class TestSortedMapBasics(unittest.TestCase):
    def test_setitem_new_and_overwrite(self):
        m = SortedMap()
        self.assertTrue(m.__setitem__("b", 2))
        self.assertFalse(m.__setitem__("b", 20))
        self.assertEqual(m["b"], 20)
        self.assertEqual(len(m), 1)

    def test_getitem_missing_raises(self):
        m = SortedMap()
        m["a"] = 1
        self.assertEqual(m["a"], 1)
        with self.assertRaises(KeyError):
            _ = m["z"]

    def test_get_default(self):
        m = SortedMap()
        m["a"] = 1
        self.assertEqual(m.get("a"), 1)
        self.assertIsNone(m.get("missing"))
        self.assertEqual(m.get("missing", 0), 0)

    def test_contains_and_len(self):
        m = SortedMap()
        for k in ("c", "a", "b"):
            m[k] = k
        self.assertIn("a", m)
        self.assertNotIn("z", m)
        self.assertEqual(len(m), 3)

    def test_keys_sorted(self):
        m = SortedMap()
        for k in ("d", "b", "a", "c"):
            m[k] = k
        self.assertEqual(m.keys(), ["a", "b", "c", "d"])

    def test_items_sorted(self):
        m = SortedMap()
        m[2] = "two"
        m[1] = "one"
        m[3] = "three"
        self.assertEqual(m.items(), [(1, "one"), (2, "two"), (3, "three")])

    def test_duplicate_key_overwrites_value_only(self):
        m = SortedMap()
        m["k"] = 1
        m["k"] = 2
        self.assertEqual(len(m), 1)
        self.assertEqual(m["k"], 2)
        self.assertEqual(m.keys(), ["k"])

    def test_none_key_rejected(self):
        m = SortedMap()
        with self.assertRaises(TypeError):
            m[None] = 1


class TestSortedMapDelete(unittest.TestCase):
    def test_delitem(self):
        m = SortedMap()
        for i in range(5):
            m[i] = i * 10
        del m[3]
        self.assertEqual(m.keys(), [0, 1, 2, 4])
        self.assertEqual(len(m), 4)

    def test_delitem_missing_raises(self):
        m = SortedMap()
        m[1] = 1
        with self.assertRaises(KeyError):
            del m[9]


class TestSortedMapRange(unittest.TestCase):
    def test_range_half_open(self):
        m = SortedMap()
        for i in range(5):
            m[i] = i * 10
        self.assertEqual(m.range(1, 4), [(1, 10), (2, 20), (3, 30)])
        self.assertEqual(
            m.range(0, 5),
            [(0, 0), (1, 10), (2, 20), (3, 30), (4, 40)],
        )

    def test_range_equal_bounds_empty(self):
        m = SortedMap()
        m[5] = "x"
        self.assertEqual(m.range(5, 5), [])

    def test_range_empty(self):
        m = SortedMap()
        m[1] = 1
        m[2] = 2
        self.assertEqual(m.range(3, 9), [])
        self.assertEqual(m.range(2, 1), [])

    def test_first(self):
        m = SortedMap()
        self.assertIsNone(m.first())
        m["z"] = 1
        m["a"] = 2
        self.assertEqual(m.first(), ("a", 2))


if __name__ == "__main__":
    unittest.main()