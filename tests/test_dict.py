"""ttlidx 现有增量行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from ttlidx.index import DictIndex


class TestDictIndex(unittest.TestCase):
    def test_set_and_get(self):
        idx = DictIndex()
        idx.set("a", {"name": "ann", "tag": 1})
        self.assertEqual(idx.get("a"), {"name": "ann", "tag": 1})

    def test_get_returns_copy(self):
        idx = DictIndex()
        idx.set("a", {"name": "ann"})
        out = idx.get("a")
        out["name"] = "mutated"
        self.assertEqual(idx.get("a"), {"name": "ann"})

    def test_set_copies_fields(self):
        idx = DictIndex()
        source = {"name": "ann"}
        idx.set("a", source)
        source["name"] = "mutated"
        self.assertEqual(idx.get("a"), {"name": "ann"})

    def test_get_missing_returns_none(self):
        idx = DictIndex()
        self.assertIsNone(idx.get("nope"))

    def test_overwrite_keeps_position(self):
        idx = DictIndex()
        idx.set("a", {"v": 1})
        idx.set("b", {"v": 2})
        idx.set("c", {"v": 3})
        idx.set("a", {"v": 9})
        self.assertEqual(idx.keys(), ("a", "b", "c"))
        self.assertEqual(idx.get("a"), {"v": 9})

    def test_delete_hit_and_miss(self):
        idx = DictIndex()
        idx.set("a", {"v": 1})
        self.assertTrue(idx.delete("a"))
        self.assertFalse(idx.delete("a"))
        self.assertEqual(idx.keys(), ())

    def test_contains(self):
        idx = DictIndex()
        idx.set("a", {"v": 1})
        self.assertTrue(idx.contains("a"))
        self.assertFalse(idx.contains("b"))

    def test_stats_hits_and_misses(self):
        idx = DictIndex()
        idx.set("a", {"v": 1})
        idx.get("a")
        idx.get("a")
        idx.get("missing")
        s = idx.stats()
        self.assertEqual(s["live"], 1)
        self.assertEqual(s["hits"], 2)
        self.assertEqual(s["misses"], 1)

    def test_stats_returns_fresh_dict(self):
        idx = DictIndex()
        s = idx.stats()
        s["live"] = 99
        self.assertEqual(idx.stats()["live"], 0)

    def test_len(self):
        idx = DictIndex()
        self.assertEqual(len(idx), 0)
        idx.set("a", {"v": 1})
        idx.set("b", {"v": 2})
        self.assertEqual(len(idx), 2)

    def test_empty_key_rejected(self):
        idx = DictIndex()
        with self.assertRaises(ValueError):
            idx.set("", {"v": 1})

    def test_non_string_key_rejected(self):
        idx = DictIndex()
        with self.assertRaises(ValueError):
            idx.set(1, {"v": 1})

    def test_non_dict_fields_rejected(self):
        idx = DictIndex()
        with self.assertRaises(ValueError):
            idx.set("a", ["v", 1])

    def test_empty_field_name_rejected(self):
        idx = DictIndex()
        with self.assertRaises(ValueError):
            idx.set("a", {"": 1})

    def test_get_non_string_key_rejected(self):
        idx = DictIndex()
        with self.assertRaises(ValueError):
            idx.get(3)


if __name__ == "__main__":
    unittest.main()
