"""OrderedMap 现有行为的锁定测试。"""

import unittest

from skiplist.ordered import OrderedMap


class TestOrderedMap(unittest.TestCase):
    def test_put_new_and_overwrite(self):
        m = OrderedMap()
        self.assertTrue(m.put("b", 2))
        self.assertFalse(m.put("b", 20))
        self.assertEqual(m.get("b"), 20)
        self.assertEqual(len(m), 1)

    def test_get_default(self):
        m = OrderedMap()
        m.put("a", 1)
        self.assertEqual(m.get("a"), 1)
        self.assertIsNone(m.get("missing"))
        self.assertEqual(m.get("missing", 0), 0)

    def test_contains_and_len(self):
        m = OrderedMap()
        for k in ("c", "a", "b"):
            m.put(k, k)
        self.assertIn("a", m)
        self.assertNotIn("z", m)
        self.assertEqual(len(m), 3)

    def test_keys_sorted(self):
        m = OrderedMap()
        for k in ("d", "b", "a", "c"):
            m.put(k, k)
        self.assertEqual(m.keys(), ["a", "b", "c", "d"])

    def test_items_sorted(self):
        m = OrderedMap()
        m.put(2, "two")
        m.put(1, "one")
        m.put(3, "three")
        self.assertEqual(m.items(), [(1, "one"), (2, "two"), (3, "three")])

    def test_range_scan_inclusive(self):
        m = OrderedMap()
        for i in range(5):
            m.put(i, i * 10)
        self.assertEqual(m.range_scan(1, 3), [(1, 10), (2, 20), (3, 30)])
        self.assertEqual(m.range_scan(0, 4), [(0, 0), (1, 10), (2, 20), (3, 30), (4, 40)])

    def test_range_scan_equal_bounds(self):
        m = OrderedMap()
        m.put(5, "x")
        self.assertEqual(m.range_scan(5, 5), [(5, "x")])

    def test_range_scan_empty(self):
        m = OrderedMap()
        m.put(1, 1)
        m.put(2, 2)
        self.assertEqual(m.range_scan(3, 9), [])
        self.assertEqual(m.range_scan(2, 1), [])

    def test_first(self):
        m = OrderedMap()
        self.assertIsNone(m.first())
        m.put("z", 1)
        m.put("a", 2)
        self.assertEqual(m.first(), ("a", 2))


if __name__ == "__main__":
    unittest.main()
