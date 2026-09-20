"""每层布隆过滤器与 MemTable 协作的新行为测试。"""

import os
import tempfile
import unittest

from blooms.table import MemTable


class CountingDict(dict):
    """统计自身被查询次数的 dict：过滤器跳过就不会进来。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lookup_count = 0

    def __contains__(self, key):
        self.lookup_count += 1
        return super().__contains__(key)


def _build_table(keys):
    t = MemTable(level_capacity=4, ratio=2, error_rate=0.01)
    for i, key in enumerate(keys):
        t.put(key, i)
    return t


class TestMemTableFilters(unittest.TestCase):
    def test_absent_key_skips_every_level_without_scanning(self):
        t = _build_table([f"k{i}" for i in range(40)])
        counters = [CountingDict(level) for level in t._levels]
        t._levels = counters
        levels_before = len(counters)
        self.assertGreater(levels_before, 1)

        self.assertIsNone(t.get("definitely-absent-xyz"))

        stats = t.stats()
        self.assertEqual(stats["filter_skips"], levels_before)
        self.assertEqual(stats["filter_probes"], 0)
        self.assertEqual(stats["misses"], 1)
        # 过滤器说肯定没有：层 dict 一次都没被查，扫描真省了
        self.assertEqual(sum(c.lookup_count for c in counters), 0)

    def test_probe_counts_scanned_levels(self):
        t = _build_table([f"k{i}" for i in range(40)])
        t.get("k0")  # k0 在最深一层，中间都是压实后的空层：空层过滤器全跳过
        stats = t.stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["filter_probes"], 1)
        self.assertEqual(stats["filter_skips"], stats["levels"] - 1)

        t.put("fresh", -1)
        t.get("fresh")  # 命中最新层，立刻停手：一探一中，零跳过
        stats = t.stats()
        self.assertEqual(stats["filter_probes"], 2)
        self.assertEqual(stats["filter_skips"], stats["levels"] - 1)

    def test_no_false_negative_after_repeated_compaction(self):
        # 键会跨层流动、被新值覆盖；压实重建后一个键都不能丢
        t = MemTable(level_capacity=3, ratio=2, error_rate=0.01)
        keys = [f"key-{i}" for i in range(150)]
        for i, key in enumerate(keys):
            t.put(key, i)
        for i, key in enumerate(keys):
            self.assertEqual(t.get(key), i)

        # 再制造一次合并 + 覆盖：刚并进去的键必须仍能命中
        t.put("key-0", 999)
        t.put("key-77", 888)
        for i, key in enumerate(keys):
            expected = 999 if key == "key-0" else 888 if key == "key-77" else i
            self.assertEqual(t.get(key), expected)

        # 每个过滤器看到的条目数都应与所在层一致，且无假阴
        for level, filter_, info in zip(t._levels, t._filters, t.filter_stats()):
            self.assertEqual(info["items"], len(level))
            for key in level:
                self.assertTrue(filter_.might_contain(key))

    def test_filters_not_saturated_under_level_capacities(self):
        # 容量按各层上限建，压实后重建：过滤器不该一路烂在饱和里
        t = MemTable(level_capacity=4, ratio=2, error_rate=0.01)
        for i in range(300):
            t.put(f"k{i}", i)
        for index, info in enumerate(t.filter_stats()):
            self.assertLessEqual(info["items"], t._capacity_of(index))
            self.assertFalse(info["saturated"])
            self.assertLess(info["estimated_false_positive_rate"], 0.02)

    def test_growth_path_rebuilds_without_false_negatives(self):
        # level_capacity=1：L0 每写第二个新键就得扩容重建，
        # 随后压实；验证扩容路径不会把已有键搞丢
        t = MemTable(level_capacity=1, ratio=2, error_rate=0.01)
        for i in range(30):
            t.put(i, i)
        for i in range(30):
            self.assertEqual(t.get(i), i)

    def test_save_load_round_trip_keeps_behavior_and_stats(self):
        t = MemTable(level_capacity=4, ratio=2, error_rate=0.02)
        for i in range(60):
            t.put(f"k{i}", i)
        t.get("k0")
        t.get("k59")
        t.get("absent-aaa")
        t.get("absent-bbb")
        stats_before = t.stats()
        filter_before = t.filter_stats()
        levels_before = t.levels()

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "table.json")
            t.save(path)
            loaded = MemTable.load(path)

        self.assertEqual(loaded.levels(), levels_before)
        self.assertEqual(len(loaded), len(t))
        self.assertEqual(loaded.stats(), stats_before)
        self.assertEqual(loaded.filter_stats(), filter_before)

        # 读回后行为一致：空查继续跳层，已有键继续命中
        skips_before = loaded.stats()["filter_skips"]
        probes_before = loaded.stats()["filter_probes"]
        self.assertIsNone(loaded.get("absent-ccc"))
        stats_after = loaded.stats()
        self.assertEqual(stats_after["filter_skips"], skips_before + stats_after["levels"])
        self.assertEqual(stats_after["filter_probes"], probes_before)
        self.assertEqual(loaded.get("k30"), 30)

        # 读回后继续写入、压实也不出假阴
        for i in range(60, 90):
            loaded.put(f"k{i}", i)
        for i in range(90):
            self.assertEqual(loaded.get(f"k{i}"), i)

    def test_load_rejects_tampered_params(self):
        t = MemTable(level_capacity=4, ratio=2, error_rate=0.02)
        t.put("a", 1)
        import json

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "table.json")
            t.save(path)
            with open(path, encoding="utf-8") as handle:
                image = json.load(handle)
            image["params"]["error_rate"] = 0.5
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(image, handle)
            with self.assertRaises(ValueError):
                MemTable.load(path)

    def test_invalid_error_rate_raises(self):
        for bad in (0.0, 1.0, -0.01):
            with self.assertRaises(ValueError):
                MemTable(error_rate=bad)

    def test_stats_expose_filter_fields(self):
        t = MemTable(error_rate=0.05)
        t.put("a", 1)
        t.get("missing")
        s = t.stats()
        self.assertEqual(s["error_rate"], 0.05)
        self.assertIn("filter_probes", s)
        self.assertIn("filter_skips", s)
        self.assertIn("estimated_false_positive_rate", s)
        self.assertLess(s["estimated_false_positive_rate"], 0.05)


if __name__ == "__main__":
    unittest.main()
