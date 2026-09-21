"""双源合流续传的新行为测试：续传、乱序窗口、损坏回退、分路背压。"""

import os
import tempfile
import unittest

from resumex.resume import BackpressureSink, MergedStreamRunner, WatermarkStore
from resumex.stream import MemorySink, MemorySource, Record


class CountingSource:
    """记录 fetch 次数与 after_seq 的来源包装。"""

    def __init__(self, source):
        self._source = source
        self.fetch_calls = 0
        self.after_seqs = []

    def append(self, seq, payload):
        self._source.append(seq, payload)

    def fetch(self, after_seq, limit):
        self.fetch_calls += 1
        self.after_seqs.append(after_seq)
        return self._source.fetch(after_seq, limit)


def seqs(received):
    return [record.seq for record in received]


class TestDualSourceResume(unittest.TestCase):
    def test_merge_then_resume_from_same_watermark_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "watermark.log")
            source_a = MemorySource([(1, "a1"), (3, "a3"), (5, "a5"), (7, "a7")])
            source_b = MemorySource([(2, "b2"), (4, "b4"), (6, "b6")])
            sink_a = BackpressureSink()
            sink_b = BackpressureSink()
            runner = MergedStreamRunner(
                {"a": source_a, "b": source_b},
                {"a": sink_a, "b": sink_b},
                path,
                batch_size=2,
                window=10,
            )
            self.assertEqual(runner.run(), 7)
            got = sorted(seqs(sink_a.received()) + seqs(sink_b.received()))
            self.assertEqual(got, [1, 2, 3, 4, 5, 6, 7])

            # “重启”：新 runner 读同一份水位，已确认的不再取。
            source_a.append(9, "a9")
            source_b.append(8, "b8")
            runner2 = MergedStreamRunner(
                {"a": source_a, "b": source_b},
                {"a": sink_a, "b": sink_b},
                path,
                batch_size=2,
                window=10,
            )
            self.assertEqual(runner2.run(), 2)
            progress = runner2.progress()
            self.assertEqual(progress["positions"], {"a": 9, "b": 8})
            self.assertEqual(progress["global_watermark"], 9)
            got = sorted(seqs(sink_a.received()) + seqs(sink_b.received()))
            self.assertEqual(got, [1, 2, 3, 4, 5, 6, 7, 8, 9])
            self.assertEqual(len(got), len(set(got)))  # 早收过的不重喂

    def test_each_source_fetches_after_its_own_watermark(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "watermark.log")
            source_a = CountingSource(MemorySource([(1, "a1"), (5, "a5")]))
            source_b = CountingSource(MemorySource([(2, "b2"), (6, "b6")]))
            sinks = {"a": BackpressureSink(), "b": BackpressureSink()}
            MergedStreamRunner(
                {"a": source_a, "b": source_b}, sinks, path, batch_size=1, window=10
            ).run()
            source_a.append(9, "a9")
            source_b.append(8, "b8")
            calls_a_before = source_a.fetch_calls
            calls_b_before = source_b.fetch_calls
            MergedStreamRunner(
                {"a": source_a, "b": source_b}, sinks, path, batch_size=1, window=10
            ).run()
            self.assertEqual(source_a.after_seqs[calls_a_before], 5)
            self.assertEqual(source_b.after_seqs[calls_b_before], 6)


class TestOrderWindow(unittest.TestCase):
    def _global_ahead_runner(self, path, window, sink_b):
        source_a = MemorySource([(seq, "a%d" % seq) for seq in range(1, 11)])
        source_b = MemorySource()
        runner = MergedStreamRunner(
            {"a": source_a, "b": source_b},
            {"a": BackpressureSink(), "b": sink_b},
            path,
            batch_size=3,
            window=window,
        )
        runner.run()
        self.assertEqual(runner.progress()["global_watermark"], 10)
        return runner, source_b

    def test_late_record_inside_window_is_filled_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "watermark.log")
            sink_b = BackpressureSink()
            _, source_b = self._global_ahead_runner(path, 5, sink_b)
            source_b.append(5, "edge5")  # 恰在窗口下界，也算窗口内
            source_b.append(8, "late8")
            runner = MergedStreamRunner(
                {"a": MemorySource(), "b": source_b},
                {"a": BackpressureSink(), "b": sink_b},
                path,
                batch_size=3,
                window=5,
            )
            moved = runner.run()
            self.assertEqual(moved, 2)
            self.assertEqual(sink_b.received(), [Record(5, "edge5"), Record(8, "late8")])
            progress = runner.progress()
            self.assertEqual(progress["late_accepted"], 2)
            self.assertEqual(progress["dropped"], 0)

    def test_record_outside_window_is_dropped_and_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "watermark.log")
            sink_b = BackpressureSink()
            _, source_b = self._global_ahead_runner(path, 5, sink_b)
            source_b.append(4, "old4")  # 全局水位 10，窗口下界 5，4 超窗
            runner = MergedStreamRunner(
                {"a": MemorySource(), "b": source_b},
                {"a": BackpressureSink(), "b": sink_b},
                path,
                batch_size=3,
                window=5,
            )
            self.assertEqual(runner.run(), 0)
            self.assertEqual(sink_b.received(), [])
            progress = runner.progress()
            self.assertEqual(progress["dropped"], 1)
            self.assertEqual(progress["late_accepted"], 0)
            # 丢了也确认过位置，重启不再取这条
            self.assertEqual(progress["positions"]["b"], 4)

    def test_duplicate_inside_window_is_not_pushed_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "watermark.log")
            source_a = MemorySource([(seq, "a%d" % seq) for seq in range(1, 9)])
            source_b = MemorySource([(7, "dup7")])  # 与 a 路同一序号
            sink_a = BackpressureSink()
            sink_b = BackpressureSink()
            runner = MergedStreamRunner(
                {"a": source_a, "b": source_b},
                {"a": sink_a, "b": sink_b},
                path,
                batch_size=8,
                window=10,
            )
            self.assertEqual(runner.run(), 8)  # b 的 7 重复，不计入
            self.assertEqual(seqs(sink_b.received()), [])
            self.assertEqual(runner.progress()["duplicates"], 1)


class TestWatermarkIntegrity(unittest.TestCase):
    def test_half_written_line_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wm.log")
            store = WatermarkStore(path, ["a", "b"])
            store.commit("a", 5)
            store.commit("b", 6)
            with open(path, "ab") as handle:
                handle.write(b"rx1|a|99|12.5|deadbeef")  # 无换行的半截
            reloaded = WatermarkStore(path, ["a", "b"])
            self.assertEqual(reloaded.position("a"), 5)
            self.assertEqual(reloaded.position("b"), 6)
            stats = reloaded.stats()
            self.assertEqual(stats["repairs"], 1)
            self.assertEqual(stats["bad_lines"], 1)

    def test_corrupt_file_rolls_back_to_last_good_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wm.log")
            store = WatermarkStore(path, ["a", "b"])
            store.commit("a", 5)
            with open(path, "ab") as handle:
                handle.write(b"rx1|b|6|1.0|00badmac000000000000000000000000000000000000000000000000000000\n")
                handle.write(b"garbage-after-corruption\n")
            reloaded = WatermarkStore(path, ["a", "b"])
            # 坏行之后的内容一律不信，退回坏行之前的完好点
            self.assertEqual(reloaded.position("a"), 5)
            self.assertEqual(reloaded.position("b"), 0)
            self.assertEqual(reloaded.stats()["repairs"], 1)
            reloaded.commit("b", 7)
            again = WatermarkStore(path, ["a", "b"])
            self.assertEqual(again.position("a"), 5)
            self.assertEqual(again.position("b"), 7)
            self.assertEqual(again.stats()["repairs"], 0)


class TestPerRouteBackpressure(unittest.TestCase):
    def test_slow_sink_only_blocks_its_own_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wm.log")
            source_a = CountingSource(MemorySource([(1, "a1"), (3, "a3"), (5, "a5")]))
            source_b = CountingSource(MemorySource([(2, "b2"), (4, "b4"), (6, "b6")]))
            sink_a = BackpressureSink()
            sink_b = BackpressureSink()
            sink_a.set_blocked(True)
            runner = MergedStreamRunner(
                {"a": source_a, "b": source_b},
                {"a": sink_a, "b": sink_b},
                path,
                batch_size=2,
                window=10,
            )
            self.assertEqual(runner.run(), 3)  # 只有 b 路推完
            self.assertEqual(source_a.fetch_calls, 0)  # a 路取数也停了
            self.assertEqual(seqs(sink_a.received()), [])
            self.assertEqual(seqs(sink_b.received()), [2, 4, 6])
            blocked = runner.progress()["blocked"]
            self.assertGreaterEqual(blocked["a"], 1)
            self.assertEqual(blocked["b"], 0)

            sink_a.set_blocked(False)
            runner2 = MergedStreamRunner(
                {"a": source_a._source, "b": source_b._source},
                {"a": sink_a, "b": sink_b},
                path,
                batch_size=2,
                window=10,
            )
            self.assertEqual(runner2.run(), 3)  # 恢复后 a 路补推
            self.assertEqual(seqs(sink_a.received()), [1, 3, 5])


if __name__ == "__main__":
    unittest.main()
