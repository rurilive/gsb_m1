"""MemTable 现有行为的锁定测试。"""

import unittest

from blooms.table import MemTable


class TestMemTable(unittest.TestCase):
    def test_put_then_get(self):
        t = MemTable(level_capacity=4)
        t.put("a", 1)
        self.assertEqual(t.get("a"), 1)

    def test_get_missing_returns_none(self):
        t = MemTable(level_capacity=4)
        t.put("a", 1)
        self.assertIsNone(t.get("nope"))

    def test_overwrite_within_newest_level(self):
        t = MemTable(level_capacity=4)
        t.put("a", 1)
        t.put("a", 2)
        self.assertEqual(t.get("a"), 2)
        self.assertEqual(len(t.levels()), 1)
        self.assertEqual(len(t), 1)

    def test_compaction_keeps_everything_readable(self):
        t = MemTable(level_capacity=2, ratio=4)
        for i, k in enumerate("abc"):
            t.put(k, i)
        # 第 0 层放不下 3 条，整体压进第 1 层
        levels = t.levels()
        self.assertEqual(len(levels), 2)
        self.assertEqual(levels[0], {})
        self.assertEqual(levels[1], {"a": 0, "b": 1, "c": 2})
        for i, k in enumerate("abc"):
            self.assertEqual(t.get(k), i)

    def test_cascade_pushes_through_multiple_levels(self):
        t = MemTable(level_capacity=1, ratio=2)
        for i, k in enumerate("abcd"):
            t.put(k, i)
        levels = t.levels()
        self.assertEqual(len(levels), 3)
        self.assertEqual(levels[0], {})
        self.assertEqual(levels[1], {})
        self.assertEqual(levels[2], {"a": 0, "b": 1, "c": 2, "d": 3})

    def test_newer_value_wins_after_compaction(self):
        t = MemTable(level_capacity=2, ratio=4)
        for i, k in enumerate("abc"):
            t.put(k, i)
        t.put("a", 99)          # 重新写回最新一层
        levels = t.levels()
        self.assertEqual(levels[0], {"a": 99})
        self.assertEqual(levels[1], {"a": 0, "b": 1, "c": 2})
        self.assertEqual(t.get("a"), 99)
        self.assertEqual(t.get("b"), 1)

    def test_levels_returns_snapshots(self):
        t = MemTable(level_capacity=4)
        t.put("a", 1)
        snap = t.levels()
        snap[0]["a"] = 999
        snap.append({"x": 1})
        self.assertEqual(t.get("a"), 1)
        self.assertEqual(len(t.levels()), 1)

    def test_len_counts_all_levels(self):
        t = MemTable(level_capacity=2, ratio=4)
        for i, k in enumerate("abc"):
            t.put(k, i)
        self.assertEqual(len(t), 3)

    def test_stats_basic(self):
        t = MemTable(level_capacity=2, ratio=4)
        t.put("a", 1)
        t.get("a")
        t.get("x")
        s = t.stats()
        self.assertEqual(s["puts"], 1)
        self.assertEqual(s["gets"], 2)
        self.assertEqual(s["hits"], 1)
        self.assertEqual(s["misses"], 1)
        self.assertEqual(s["levels"], 1)

    def test_stats_returns_fresh_dict(self):
        t = MemTable(level_capacity=2)
        s = t.stats()
        s["hits"] = 99
        self.assertEqual(t.stats()["hits"], 0)

    def test_invalid_level_capacity_raises(self):
        with self.assertRaises(ValueError):
            MemTable(level_capacity=0)

    def test_ratio_below_two_raises(self):
        with self.assertRaises(ValueError):
            MemTable(level_capacity=2, ratio=1)


if __name__ == "__main__":
    unittest.main()
