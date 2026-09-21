"""compact_once 现有行为的锁定测试：挑谁、并完什么账、重启后还在不在。"""

import unittest

from segpile import MemoryBackend, SimDevice, Store
from segpile.segment import merge_pairs, merge_units


def fill(store, count, prefix="a", start=0):
    """按顺序写 count 个 key，写满就滚段。"""
    for i in range(count):
        store.put("%s%02d" % (prefix, start + i), start + i)


def make_store(limit):
    return Store(MemoryBackend(), SimDevice(), segment_limit=limit)


class SmallCase(unittest.TestCase):
    """limit=4，两个段：一个写满的旧段加一个刚开的活动段。"""

    def test_none_when_active_is_the_only_partner(self):
        store = make_store(4)
        fill(store, 5)
        self.assertEqual([(s.sid, s.seq, s.size) for s in store.segments()], [(0, 0, 4), (1, 1, 1)])
        # 活动段不算够格，剩下只有一个候选，压不动
        self.assertIsNone(store.compact_once())
        self.assertEqual([(s.sid, s.seq, s.size) for s in store.segments()], [(0, 0, 4), (1, 1, 1)])


class CompactCase(unittest.TestCase):
    """limit=8，写入 36 个 key，得到 5 段。"""

    def setUp(self):
        self.backend = MemoryBackend()
        self.device = SimDevice()
        self.store = Store(self.backend, self.device, segment_limit=8)
        fill(self.store, 36)

    def layout(self):
        return [(s.sid, s.seq, s.size) for s in self.store.segments()]


class TestPickPolicy(CompactCase):
    def test_picks_two_smallest_oldest_first_on_tie(self):
        self.assertEqual(
            self.layout(),
            [(0, 0, 8), (1, 1, 8), (2, 2, 8), (3, 3, 8), (4, 4, 4)],
        )
        self.assertEqual(self.store.active.sid, 4)
        report = self.store.compact_once()
        self.assertEqual(report.inputs, (0, 1))
        self.assertEqual(report.sid, 1)
        self.assertEqual(report.seq, 1)

    def test_bigger_merged_segment_stays_out_of_next_round(self):
        self.store.compact_once()
        report = self.store.compact_once()
        self.assertEqual(report.inputs, (2, 3))
        self.assertEqual(self.layout(), [(1, 1, 16), (3, 3, 16), (4, 4, 4)])

    def test_active_segment_is_never_compacted(self):
        self.store.compact_once()
        self.store.compact_once()
        # 活动段只有 4 个 key，是最小的一段，但不参与压缩
        self.assertEqual(self.store.active.sid, 4)
        self.assertEqual(self.store.active.size, 4)


class TestMergeResult(CompactCase):
    def test_segment_count_drops_by_one(self):
        before = len(self.store.segments())
        self.store.compact_once()
        self.assertEqual(len(self.store.segments()), before - 1)

    def test_merged_segment_takes_over_newest_input_identity(self):
        self.store.compact_once()
        merged = [s for s in self.store.segments() if s.sid == 1][0]
        self.assertEqual(merged.seq, 1)
        self.assertEqual(merged.size, 16)

    def test_values_survive_overlapping_keys(self):
        self.store.put("a03", "newer")
        self.store.put("a20", "newest")
        self.store.compact_once()
        self.store.compact_once()
        # 盖在旧段里的值不许在合并后复活
        self.assertEqual(self.store.snapshot()["a03"], "newer")
        self.assertEqual(self.store.get("a03"), "newer")
        self.assertEqual(self.store.get("a20"), "newest")
        self.assertEqual(self.store.get("a00"), 0)
        self.assertEqual(self.store.get("a35"), 35)
        self.assertEqual(len(self.store.snapshot()), 36)


class TestAccounting(CompactCase):
    def test_report_fields(self):
        self.device.advance(1000)
        started = self.device.now()
        report = self.store.compact_once()
        self.assertEqual(report.inputs, (0, 1))
        self.assertEqual(report.units, 33)
        self.assertAlmostEqual(report.elapsed, 33.0)
        # 压缩占住设备，但不推进前台时钟
        self.assertAlmostEqual(self.device.now(), started)
        self.assertAlmostEqual(self.device.busy_until, started + 33.0)

    def test_device_charges_read_and_write(self):
        before = (self.device.read_units, self.device.write_units)
        report = self.store.compact_once()
        after = (self.device.read_units, self.device.write_units)
        self.assertEqual(after[0] - before[0], 16)
        self.assertEqual(after[1] - before[1], 17)
        self.assertEqual(report.units, (after[0] - before[0]) + (after[1] - before[1]))

    def test_compaction_holds_the_device(self):
        self.device.advance(1000)
        self.store.compact_once()
        # 整轮 33 个单位的占用全落在前台写头上
        self.assertAlmostEqual(self.store.put("z", 1), 34.0)


class TestPersistenceAfterCompact(CompactCase):
    def test_no_orphan_blobs(self):
        self.store.compact_once()
        self.assertEqual(
            set(self.backend.segment_ids()),
            {s.sid for s in self.store.segments()},
        )

    def test_reopen_after_compaction(self):
        self.store.compact_once()
        reopened = Store(self.backend, SimDevice(), segment_limit=8)
        self.assertEqual(
            self.layout(),
            [(s.sid, s.seq, s.size) for s in reopened.segments()],
        )
        self.assertEqual(reopened.get("a00"), 0)
        self.assertEqual(reopened.get("a35"), 35)
        self.assertEqual(reopened.active.sid, 4)


class TestMergeHelpers(unittest.TestCase):
    def test_merge_pairs_later_blob_wins(self):
        merged = merge_pairs([[(1, "a"), (2, "b")], [(2, "B"), (3, "c")]])
        self.assertEqual(merged, [(1, "a"), (2, "B"), (3, "c")])

    def test_merge_units_counts_reads_plus_result(self):
        store = make_store(4)
        fill(store, 9)
        picked = [s for s in store.segments() if s.sid in (0, 1)]
        self.assertEqual([s.size for s in picked], [4, 4])
        self.assertEqual(merge_units(picked), 8 + 8)


if __name__ == "__main__":
    unittest.main()
