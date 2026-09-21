"""MemorySource / MemorySink / StreamRunner 现有行为的锁定测试。"""

import unittest

from resumex.stream import MemorySink, MemorySource, Record, StreamRunner


class TestMemorySource(unittest.TestCase):
    def test_fetch_after_seq(self):
        source = MemorySource([(1, "a"), (2, "b"), (3, "c")])
        got = source.fetch(0, 10)
        self.assertEqual(got, [Record(1, "a"), Record(2, "b"), Record(3, "c")])

    def test_fetch_skips_records_at_or_below_after_seq(self):
        source = MemorySource([(1, "a"), (2, "b"), (3, "c")])
        self.assertEqual(source.fetch(2, 10), [Record(3, "c")])

    def test_fetch_respects_limit(self):
        source = MemorySource([(1, "a"), (2, "b"), (3, "c"), (4, "d")])
        self.assertEqual(source.fetch(0, 2), [Record(1, "a"), Record(2, "b")])

    def test_fetch_empty_when_caught_up(self):
        source = MemorySource([(1, "a")])
        self.assertEqual(source.fetch(1, 10), [])

    def test_append_extends_source(self):
        source = MemorySource([(1, "a")])
        source.append(2, "b")
        self.assertEqual(source.latest_seq, 2)
        self.assertEqual(len(source), 2)

    def test_append_rejects_non_increasing_seq(self):
        source = MemorySource([(2, "b")])
        with self.assertRaises(ValueError):
            source.append(2, "again")

    def test_latest_seq_on_empty_source(self):
        self.assertEqual(MemorySource().latest_seq, 0)

    def test_fetch_invalid_limit_raises(self):
        with self.assertRaises(ValueError):
            MemorySource([(1, "a")]).fetch(0, 0)


class TestMemorySink(unittest.TestCase):
    def test_push_records_and_advances_watermark(self):
        sink = MemorySink()
        moved = sink.push([Record(1, "a"), Record(2, "b")])
        self.assertEqual(moved, 2)
        self.assertEqual(sink.watermark, 2)
        self.assertEqual(sink.received(), [Record(1, "a"), Record(2, "b")])

    def test_stats_counts_batches(self):
        sink = MemorySink()
        sink.push([Record(1, "a")])
        sink.push([Record(2, "b")])
        s = sink.stats()
        self.assertEqual(s["batches"], 2)
        self.assertEqual(s["received"], 2)
        self.assertEqual(s["watermark"], 2)

    def test_received_returns_fresh_list(self):
        sink = MemorySink()
        sink.push([Record(1, "a")])
        snap = sink.received()
        snap.append(Record(2, "b"))
        self.assertEqual(len(sink.received()), 1)

    def test_empty_sink_watermark_is_zero(self):
        self.assertEqual(MemorySink().watermark, 0)


class TestStreamRunner(unittest.TestCase):
    def test_run_pushes_every_record_once(self):
        source = MemorySource([(1, "a"), (2, "b"), (3, "c")])
        sink = MemorySink()
        runner = StreamRunner(source, sink, batch_size=2)
        self.assertEqual(runner.run(), 3)
        self.assertEqual(sink.received(), [Record(1, "a"), Record(2, "b"), Record(3, "c")])
        self.assertEqual(sink.watermark, 3)

    def test_run_batches_by_batch_size(self):
        source = MemorySource([(i, "k%d" % i) for i in range(1, 6)])
        sink = MemorySink()
        StreamRunner(source, sink, batch_size=2).run()
        self.assertEqual(sink.stats()["batches"], 3)  # 2 + 2 + 1

    def test_run_on_empty_source_is_noop(self):
        source = MemorySource()
        sink = MemorySink()
        self.assertEqual(StreamRunner(source, sink, batch_size=2).run(), 0)
        self.assertEqual(sink.received(), [])

    def test_second_run_with_no_new_records_pushes_nothing(self):
        source = MemorySource([(1, "a"), (2, "b")])
        sink = MemorySink()
        runner = StreamRunner(source, sink, batch_size=2)
        runner.run()
        self.assertEqual(runner.run(), 0)
        self.assertEqual(len(sink.received()), 2)

    def test_run_picks_up_records_appended_between_runs(self):
        source = MemorySource([(1, "a")])
        sink = MemorySink()
        runner = StreamRunner(source, sink, batch_size=2)
        runner.run()
        source.append(2, "b")
        self.assertEqual(runner.run(), 1)
        self.assertEqual(sink.received(), [Record(1, "a"), Record(2, "b")])

    def test_progress_records_position_and_counts(self):
        source = MemorySource([(1, "a"), (2, "b"), (3, "c")])
        runner = StreamRunner(source, MemorySink(), batch_size=2)
        runner.run()
        p = runner.progress()
        self.assertEqual(p["last_seq"], 3)
        self.assertEqual(p["pushed"], 3)
        self.assertEqual(p["batches"], 2)

    def test_progress_returns_fresh_dict(self):
        runner = StreamRunner(MemorySource(), MemorySink(), batch_size=2)
        p = runner.progress()
        p["pushed"] = 99
        self.assertEqual(runner.progress()["pushed"], 0)

    def test_progress_uses_injected_clock(self):
        ticks = iter([10.0, 20.0])
        source = MemorySource([(1, "a"), (2, "b"), (3, "c")])
        runner = StreamRunner(source, MemorySink(), batch_size=2, clock=lambda: next(ticks))
        runner.run()
        self.assertEqual(runner.progress()["last_at"], 20.0)

    def test_invalid_batch_size_raises(self):
        with self.assertRaises(ValueError):
            StreamRunner(MemorySource(), MemorySink(), batch_size=0)


if __name__ == "__main__":
    unittest.main()
