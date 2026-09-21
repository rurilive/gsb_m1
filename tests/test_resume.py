"""双源续传新行为测试。

覆盖：双源合并续传、窗口内迟到补入、窗口外丢弃计数、半截水位
判废、水位文件损坏回退、分路背压。
"""

import os
import shutil
import tempfile
import unittest

from resumex.resume import BackpressureGate, MergeRunner, WatermarkStore
from resumex.stream import MemorySink, MemorySource, Record


class WatermarkStoreTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="resumex-test-")
        self.path = os.path.join(self.tmp, "watermark")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_runner(self, sources, sink=None, store=None, window=10,
                    batch_size=10, gates=None, clock=None):
        store = store or WatermarkStore(self.path)
        sink = sink or MemorySink()
        kwargs = {"window": window, "batch_size": batch_size, "gates": gates}
        if clock is not None:
            kwargs["clock"] = clock
        return MergeRunner(sources, sink, store, **kwargs), sink, store


class TestDualSourceMergeResume(WatermarkStoreTestBase):
    def test_two_sources_merge_in_one_run(self):
        sources = {
            "A": MemorySource([(1, "a1"), (3, "a3"), (5, "a5")]),
            "B": MemorySource([(2, "b2"), (4, "b4"), (6, "b6")]),
        }
        runner, sink, _ = self.make_runner(sources, batch_size=1)
        self.assertEqual(runner.run(), 6)
        self.assertEqual([r.seq for r in sink.received()], [1, 2, 3, 4, 5, 6])

    def test_merge_pushes_per_lane_per_round_and_covers_everything(self):
        sources = {
            "A": MemorySource([(1, "a1"), (3, "a3"), (5, "a5")]),
            "B": MemorySource([(2, "b2"), (4, "b4"), (6, "b6")]),
        }
        runner, sink, _ = self.make_runner(sources, batch_size=2)
        self.assertEqual(runner.run(), 6)
        # 每轮 A、B 各一批，到达顺序按路交错；全局覆盖、不重不漏。
        self.assertEqual([r.seq for r in sink.received()], [1, 3, 2, 4, 5, 6])
        self.assertEqual(sink.watermark, 6)

    def test_restart_continues_from_persisted_watermarks_without_duplicates(self):
        sources = {
            "A": MemorySource([(1, "a1"), (3, "a3"), (5, "a5"), (7, "a7")]),
            "B": MemorySource([(2, "b2"), (4, "b4"), (6, "b6"), (8, "b8")]),
        }
        sink = MemorySink()
        runner1, sink, store = self.make_runner(
            {lane: src for lane, src in sources.items()}, sink=sink, batch_size=2
        )
        self.assertEqual(runner1.run(), 8)
        self.assertEqual(store.positions(), {"A": 7, "B": 8})

        # 同一份水位文件、全新来源与搬运器模拟重启；不重喂任何旧记录。
        resumed_sources = {
            "A": MemorySource([(1, "a1"), (3, "a3"), (5, "a5"), (7, "a7"),
                               (9, "a9")]),
            "B": MemorySource([(2, "b2"), (4, "b4"), (6, "b6"), (8, "b8"),
                               (10, "b10")]),
        }
        runner2 = MergeRunner(
            resumed_sources, sink, WatermarkStore(self.path),
            batch_size=2,
        )
        self.assertEqual(runner2.run(), 2)
        seqs = [r.seq for r in sink.received()]
        self.assertEqual(sorted(seqs), list(range(1, 11)))
        self.assertEqual(len(seqs), len(set(seqs)))
        stats = runner2.stats()
        self.assertEqual(stats["duplicates"], 0)
        self.assertEqual(stats["late_accepted"], 0)
        self.assertEqual(stats["late_dropped"], 0)


class TestLateWindow(WatermarkStoreTestBase):
    def test_late_record_inside_window_is_accepted(self):
        sources = {"A": MemorySource([(1, "a1"), (10, "a10")]),
                   "B": MemorySource()}
        runner, sink, _ = self.make_runner(sources, window=5, batch_size=10)
        runner.run()
        sources["B"].append(7, "late-b7")
        self.assertEqual(runner.run(), 1)
        self.assertEqual(sink.watermark, 10)
        self.assertEqual([r.seq for r in sink.received()], [1, 10, 7])
        stats = runner.stats()
        self.assertEqual(stats["late_accepted"], 1)
        self.assertEqual(stats["late_dropped"], 0)

    def test_late_record_on_the_window_boundary_is_accepted(self):
        sources = {"A": MemorySource([(1, "a1"), (10, "a10")]),
                   "B": MemorySource()}
        runner, _, _ = self.make_runner(sources, window=5)
        runner.run()
        sources["B"].append(5, "edge-b5")
        self.assertEqual(runner.run(), 1)
        self.assertEqual(runner.stats()["late_accepted"], 1)

    def test_late_record_outside_window_is_dropped_and_counted(self):
        sources = {"A": MemorySource([(1, "a1"), (10, "a10")]),
                   "B": MemorySource()}
        runner, sink, _ = self.make_runner(sources, window=5, batch_size=10)
        runner.run()
        sources["B"].append(4, "late-b4")  # 4 < 10 - 5，超窗
        self.assertEqual(runner.run(), 0)
        self.assertEqual([r.seq for r in sink.received()], [1, 10])
        stats = runner.stats()
        self.assertEqual(stats["late_dropped"], 1)
        self.assertEqual(stats["late_accepted"], 0)

    def test_window_zero_drops_every_old_record(self):
        sources = {"A": MemorySource([(1, "a1"), (3, "a3")]),
                   "B": MemorySource()}
        runner, sink, _ = self.make_runner(sources, window=0, batch_size=1)
        runner.run()
        sources["B"].append(2, "late-b2")
        self.assertEqual(runner.run(), 0)
        self.assertEqual(runner.stats()["late_dropped"], 1)
        self.assertEqual(sink.received(), [Record(1, "a1"), Record(3, "a3")])


class TestTornWatermarkLine(WatermarkStoreTestBase):
    def test_half_written_line_is_rejected_last_good_line_kept(self):
        store = WatermarkStore(self.path)
        store.commit({"A": 5})
        store.commit({"A": 9, "B": 4})
        positions = store.positions()

        # 模拟写到一半的尾部记录：没有校验、没有换行收尾。
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("A|12|deadbe")

        reopened = WatermarkStore(self.path)
        self.assertEqual(reopened.positions(), positions)
        self.assertEqual(reopened.get("A"), 9)
        self.assertEqual(reopened.stats()["rejected_lines"], 1)
        self.assertEqual(reopened.last_recovery()[0], "primary")

    def test_line_with_bad_checksum_is_rejected(self):
        store = WatermarkStore(self.path)
        store.commit({"A": 5})
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        lines.insert(1, "B|7|00000000")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

        reopened = WatermarkStore(self.path)
        self.assertNotIn("B", reopened.positions())
        self.assertEqual(reopened.get("A"), 5)
        self.assertEqual(reopened.stats()["rejected_lines"], 1)


class TestCorruptedWatermarkFallback(WatermarkStoreTestBase):
    def test_corrupted_primary_falls_back_to_last_good_snapshot(self):
        store = WatermarkStore(self.path)
        store.commit({"A": 3, "B": 2})
        store.commit({"A": 7, "B": 6})
        self.assertTrue(os.path.exists(self.path + ".bak"))

        # 主文件整个写坏（头部都没了），.bak 仍是上一次完好点。
        with open(self.path, "wb") as handle:
            handle.write(b"\x00\x01\x02garbage-no-magic")

        reopened = WatermarkStore(self.path)
        self.assertEqual(reopened.positions(), {"A": 3, "B": 2})
        self.assertEqual(reopened.get("A"), 3)
        self.assertEqual(reopened.stats()["fallbacks"], 1)
        self.assertEqual(reopened.last_recovery(),
                         ("backup", self.path + ".bak"))

    def test_fallback_then_commit_restores_good_primary(self):
        store = WatermarkStore(self.path)
        store.commit({"A": 3, "B": 2})
        store.commit({"A": 7, "B": 6})
        with open(self.path, "wb") as handle:
            handle.write(b"broken")

        reopened = WatermarkStore(self.path)
        reopened.commit({"A": 8, "B": 6})
        again = WatermarkStore(self.path)
        self.assertEqual(again.positions(), {"A": 8, "B": 6})
        self.assertEqual(again.last_recovery()[0], "primary")

    def test_missing_primary_loads_backup(self):
        store = WatermarkStore(self.path)
        store.commit({"A": 1})
        store.commit({"A": 4})
        os.unlink(self.path)

        reopened = WatermarkStore(self.path)
        self.assertEqual(reopened.get("A"), 1)
        self.assertEqual(reopened.stats()["fallbacks"], 1)


class TestPerLaneBackpressure(WatermarkStoreTestBase):
    def test_blocked_lane_pauses_alone_other_lane_keeps_pushing(self):
        sources = {
            "A": MemorySource([(1, "a1"), (3, "a3"), (5, "a5"), (7, "a7")]),
            "B": MemorySource([(2, "b2"), (4, "b4"), (6, "b6"), (8, "b8")]),
        }
        gate_b = BackpressureGate()
        gate_b.close()
        runner, sink, store = self.make_runner(
            sources, window=100, batch_size=10, gates={"B": gate_b}
        )

        pushed = runner.run()
        self.assertEqual(pushed, 4)
        self.assertEqual([r.seq for r in sink.received()], [1, 3, 5, 7])
        # B 一条没取、水位没动；A 已确认落盘。
        self.assertEqual(store.get("A"), 7)
        self.assertEqual(store.get("B"), 0)
        stats = runner.stats()
        self.assertGreater(stats["gates"]["B"]["blocked_rounds"], 0)
        self.assertEqual(stats["gates"]["A"]["blocked_rounds"], 0)
        self.assertEqual(stats["fetched"]["B"], 0)

        # 下游恢复后，B 接着自己的水位取；A 无新数据不重喂。
        gate_b.open()
        self.assertEqual(runner.run(), 4)
        self.assertEqual([r.seq for r in sink.received()],
                         [1, 3, 5, 7, 2, 4, 6, 8])
        self.assertEqual(store.positions(), {"A": 7, "B": 8})

    def test_late_records_while_blocked_are_recovered_inside_window(self):
        sources = {"A": MemorySource(), "B": MemorySource()}
        gate_b = BackpressureGate()
        gate_b.close()
        runner, sink, _ = self.make_runner(
            sources, window=5, batch_size=10, gates={"B": gate_b}
        )
        sources["A"].append(1, "a1")
        sources["A"].append(10, "a10")
        # 被挡住的 B 在 A 推进期间陆续“到达”迟到数据。
        sources["B"].append(8, "b8")
        sources["B"].append(9, "b9")
        runner.run()

        gate_b.open()
        self.assertEqual(runner.run(), 2)
        self.assertEqual(sorted(r.seq for r in sink.received()),
                         [1, 8, 9, 10])
        self.assertEqual(runner.stats()["late_accepted"], 2)


if __name__ == "__main__":
    unittest.main()
