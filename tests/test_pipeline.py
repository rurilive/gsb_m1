"""批处理管道的新行为测试：组合语义、批冲刷、背压、错误策略与计数。"""

import threading
import time
import unittest

from pipeflow import (
    Batch,
    CollectSink,
    Filter,
    FlatMap,
    IterSource,
    Map,
    Pipeline,
    Sink,
    Source,
    StageStats,
)


class FakeClock:
    """可手动推进的假时钟，用来确定性地触发 Batch 的超时冲刷。"""

    def __init__(self, t=0.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class TimedSource(Source):
    """按给定间隔推进假时钟后逐条产出的源头。"""

    def __init__(self, n, clock, step):
        self.n = n
        self.clock = clock
        self.step = step

    def iter_items(self):
        for i in range(self.n):
            self.clock.advance(self.step)
            yield i


class TestComposition(unittest.TestCase):
    def test_map_filter_chain_preserves_order(self):
        sink = CollectSink()
        pipeline = Pipeline(
            IterSource([1, 2, 3, 4, 5]),
            [Map(lambda x: x * 2), Filter(lambda x: x % 4 == 0)],
            sink,
            capacity=2,
        )
        stats = pipeline.run()
        self.assertEqual(sink.items, [4, 8])
        self.assertEqual(stats.processed, 2)

    def test_flatmap_expands(self):
        sink = CollectSink()
        Pipeline(IterSource([1, 2]), [FlatMap(lambda x: [x, x * 10])], sink).run()
        self.assertEqual(sink.items, [1, 10, 2, 20])

    def test_flatmap_can_drop_all(self):
        sink = CollectSink()
        Pipeline(IterSource([1, 2, 3]), [FlatMap(lambda x: [])], sink).run()
        self.assertEqual(sink.items, [])

    def test_add_is_chainable(self):
        sink = CollectSink()
        Pipeline(IterSource([1, 2, 3]), [], sink).add(Map(lambda x: x + 1)).add(
            Filter(lambda x: x > 2)
        ).run()
        self.assertEqual(sink.items, [3, 4])

    def test_no_stage_passthrough(self):
        sink = CollectSink()
        stats = Pipeline(IterSource([1, 2, 3]), [], sink).run()
        self.assertEqual(sink.items, [1, 2, 3])
        self.assertEqual(stats.processed, 3)

    def test_run_returns_stats_type(self):
        stats = Pipeline(IterSource([1]), [], CollectSink()).run()
        self.assertIsInstance(stats, StageStats)

    def test_run_twice_raises(self):
        pipeline = Pipeline(IterSource([1]), [], CollectSink())
        pipeline.run()
        with self.assertRaises(RuntimeError):
            pipeline.run()

    def test_empty_source(self):
        sink = CollectSink()
        stats = Pipeline(IterSource([]), [Batch(3), Map(lambda x: x)], sink).run()
        self.assertEqual(stats.processed, 0)
        self.assertEqual(sink.items, [])


class TestBatchFlush(unittest.TestCase):
    def test_flush_on_size(self):
        groups = []

        def collect(batch):
            groups.append(list(batch))
            return batch

        sink = CollectSink()
        Pipeline(IterSource(range(9)), [Batch(4, batch_func=collect)], sink).run()
        self.assertEqual(groups, [[0, 1, 2, 3], [4, 5, 6, 7], [8]])
        self.assertEqual(sink.items, list(range(9)))

    def test_partial_batch_flushed_at_end(self):
        sink = CollectSink()
        Pipeline(IterSource(range(5)), [Batch(2)], sink).run()
        self.assertEqual(sink.items, [0, 1, 2, 3, 4])

    def test_flush_on_timeout(self):
        groups = []
        clock = FakeClock()

        def collect(batch):
            groups.append(list(batch))
            return batch

        # 每 0.5 秒产出一条，超时 1.2：攒到 3 条时下一条已间隔 1.5 秒，先冲
        pipeline = Pipeline(
            TimedSource(9, clock, 0.5),
            [Batch(4, batch_func=collect, timeout=1.2)],
            CollectSink(),
            clock=clock,
            capacity=4,
        )
        pipeline.run()
        self.assertEqual(groups, [[0, 1, 2], [3, 4, 5], [6, 7, 8]])

    def test_slow_producer_timeout_flushes_singletons(self):
        groups = []
        clock = FakeClock()

        def collect(batch):
            groups.append(list(batch))
            return batch

        pipeline = Pipeline(
            TimedSource(5, clock, 2.0),
            [Batch(3, batch_func=collect, timeout=1.0)],
            CollectSink(),
            clock=clock,
            capacity=4,
        )
        pipeline.run()
        self.assertEqual(groups, [[0], [1], [2], [3], [4]])

    def test_timeout_none_only_size(self):
        groups = []

        def collect(batch):
            groups.append(list(batch))
            return batch

        Pipeline(IterSource(range(5)), [Batch(2, batch_func=collect)], CollectSink()).run()
        self.assertEqual(groups, [[0, 1], [2, 3], [4]])

    def test_batch_size_must_be_positive(self):
        for bad in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                Batch(bad)

    def test_pending_tracks_buffer(self):
        batch = Batch(3)
        self.assertEqual(batch.pending, 0)
        batch.flush()
        self.assertEqual(batch.pending, 0)


class TestBackpressure(unittest.TestCase):
    def test_invalid_capacity_fails_fast(self):
        for bad in (0, -1, 1.5, True, "4"):
            with self.assertRaises(ValueError):
                Pipeline(IterSource([]), [], CollectSink(), capacity=bad)

    def test_slow_sink_bounds_read_ahead(self):
        produced = []
        lock = threading.Lock()

        class CountingSource(Source):
            def __init__(self, n):
                self.n = n

            def iter_items(self):
                for i in range(self.n):
                    with lock:
                        produced.append(i)
                    yield i

        class SlowSink(Sink):
            def __init__(self):
                self.count = 0

            def consume(self, value):
                self.count += 1
                if self.count <= 3:
                    time.sleep(0.15)

        sink = SlowSink()
        pipeline = Pipeline(
            CountingSource(80), [Map(lambda x: x)], sink, capacity=2
        )
        runner = threading.Thread(target=pipeline.run)
        runner.start()
        peak = 0
        for _ in range(5):
            time.sleep(0.08)
            with lock:
                peak = max(peak, len(produced))
        runner.join()
        # 下游慢时上游只多读有限几条，不会把 80 条一次读完
        self.assertLess(peak, 20)
        self.assertEqual(sink.count, 80)

    def test_capacity_one_still_delivers_everything(self):
        sink = CollectSink()
        stats = Pipeline(
            IterSource(range(20)), [Map(lambda x: x)], sink, capacity=1
        ).run()
        self.assertEqual(sink.items, list(range(20)))
        self.assertEqual(stats.processed, 20)


class TestErrorPolicies(unittest.TestCase):
    @staticmethod
    def _boom_on(target):
        def func(value):
            if value == target:
                raise ValueError("boom on %r" % (target,))
            return value

        return func

    def test_abort_raises_and_propagates(self):
        sink = CollectSink()
        pipeline = Pipeline(
            IterSource([1, 2, 3]), [Map(self._boom_on(2))], sink, policy="abort"
        )
        with self.assertRaises(ValueError):
            pipeline.run()

    def test_default_policy_is_abort(self):
        pipeline = Pipeline(IterSource([1, 2, 3]), [Map(self._boom_on(2))], CollectSink())
        with self.assertRaises(ValueError):
            pipeline.run()

    def test_skip_counts_and_continues(self):
        sink = CollectSink()
        stats = Pipeline(
            IterSource([1, 2, 3]), [Map(self._boom_on(2))], sink, policy="skip"
        ).run()
        self.assertEqual(sink.items, [1, 3])
        self.assertEqual(stats.processed, 2)
        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.failed, 0)

    def test_retry_succeeds_within_budget(self):
        attempts = {}

        def flaky(value):
            attempts[value] = attempts.get(value, 0) + 1
            if value == 2 and attempts[value] < 3:
                raise ValueError("transient")
            return value

        sink = CollectSink()
        stats = Pipeline(
            IterSource([1, 2, 3]), [Map(flaky)], sink, policy="retry", retries=5
        ).run()
        self.assertEqual(sink.items, [1, 2, 3])
        self.assertEqual(stats.processed, 3)
        self.assertEqual(stats.failed, 0)

    def test_retry_exhausted_counts_failed(self):
        sink = CollectSink()
        stats = Pipeline(
            IterSource([1, 2, 3]),
            [Map(self._boom_on(2))],
            sink,
            policy="retry",
            retries=2,
        ).run()
        self.assertEqual(sink.items, [1, 3])
        self.assertEqual(stats.processed, 2)
        self.assertEqual(stats.failed, 1)

    def test_retries_must_be_non_negative(self):
        with self.assertRaises(ValueError):
            Pipeline(IterSource([]), [], CollectSink(), policy="retry", retries=-1)

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            Pipeline(IterSource([]), [], CollectSink(), policy="drop")

    def test_counts_reconcile(self):
        def half_bad(value):
            if value % 2 == 0:
                raise ValueError("even")
            return value

        sink = CollectSink()
        stats = Pipeline(
            IterSource(range(10)), [Map(half_bad)], sink, policy="skip"
        ).run()
        self.assertEqual(stats.processed + stats.skipped + stats.failed, 10)
        self.assertEqual(stats.processed, 5)
        self.assertEqual(stats.skipped, 5)


class TestValidation(unittest.TestCase):
    def test_timeout_must_be_non_negative_number(self):
        for bad in (-1, -0.5, "2", True):
            with self.assertRaises(ValueError):
                Pipeline(IterSource([]), [], CollectSink(), timeout=bad)

    def test_timeout_none_and_positive_ok(self):
        Pipeline(IterSource([]), [], CollectSink(), timeout=None)
        Pipeline(IterSource([]), [], CollectSink(), timeout=1.0)

    def test_batch_timeout_validation(self):
        Batch(2, timeout=None)
        Batch(2, timeout=0.0)
        with self.assertRaises(ValueError):
            Batch(2, timeout=-1)


if __name__ == "__main__":
    unittest.main()