"""调用链上下文的锁定测试：并发隔离、嵌套计时、报告结构。"""

import threading
import time
import unittest

from tracectx import (
    TracedThread,
    TracedThreadPoolExecutor,
    async_call,
    begin_chain,
    correlation_id,
    current_span,
    format_report,
    get_slow_threshold,
    map_batch,
    run_detached,
    set_slow_threshold,
    span,
)


class TestCorrelationIsolation(unittest.TestCase):
    def test_no_chain_means_no_id(self):
        self.assertIsNone(correlation_id())
        self.assertIsNone(current_span())

    def test_id_generated_and_reset_on_exit(self):
        with begin_chain() as chain:
            self.assertEqual(correlation_id(), chain.correlation_id)
            self.assertTrue(chain.correlation_id)
        self.assertIsNone(correlation_id())

    def test_nested_chain_rejected(self):
        with begin_chain():
            with self.assertRaises(RuntimeError):
                with begin_chain():
                    pass

    def test_concurrent_chains_keep_own_ids(self):
        barrier = threading.Barrier(4, timeout=5)
        seen = {}
        lock = threading.Lock()

        def worker(name):
            with begin_chain(correlation_id="chain-" + name):
                barrier.wait()
                ids = [correlation_id()]
                inner = TracedThread(target=lambda: ids.append(correlation_id()))
                inner.start()
                inner.join(5)
                time.sleep(0.01)  # 给别的链路留干扰窗口
                ids.append(correlation_id())
                with lock:
                    seen[name] = ids

        threads = [
            threading.Thread(target=worker, args=(str(i),)) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(5)
        self.assertEqual(sorted(seen), ["0", "1", "2", "3"])
        for name, ids in seen.items():
            self.assertEqual(ids, ["chain-" + name] * 3)

    def test_pool_tasks_carry_submitters_chain(self):
        barrier = threading.Barrier(4, timeout=5)

        def task():
            barrier.wait()
            return correlation_id()

        futures = []
        with TracedThreadPoolExecutor(max_workers=4) as ex:
            for i in range(4):
                with begin_chain(correlation_id="c%d" % i):
                    futures.append(("c%d" % i, ex.submit(task)))
            for want, fut in futures:
                self.assertEqual(fut.result(5), want)

    def test_detached_and_async_carry_id(self):
        box = []
        done = threading.Event()
        with begin_chain(correlation_id="d1"):
            self.assertEqual(run_detached(correlation_id), "d1")
            t = async_call(
                correlation_id,
                on_done=lambda v: (box.append(v), done.set()),
            )
            self.assertTrue(done.wait(5))
            t.join(5)
        self.assertEqual(box, ["d1"])


class TestSpanTiming(unittest.TestCase):
    def test_nested_timing_and_restore(self):
        with begin_chain("t"):
            with span("outer") as outer:
                time.sleep(0.02)
                with span("inner") as inner:
                    time.sleep(0.01)
                self.assertIs(current_span(), outer)
            self.assertIsNone(current_span())
        self.assertIs(inner.parent, outer)
        self.assertEqual([c.name for c in outer.children], ["inner"])
        self.assertGreaterEqual(inner.elapsed, 0.005)
        self.assertGreaterEqual(outer.elapsed, inner.elapsed)

    def test_child_span_across_thread_attaches_to_parent(self):
        def work():
            with span("child"):
                time.sleep(0.01)

        with begin_chain("x") as chain:
            with span("parent") as parent:
                t = TracedThread(target=work)
                t.start()
                t.join(5)
                with span("sibling"):
                    pass
        self.assertEqual(chain.roots, [parent])
        names = sorted(c.name for c in parent.children)
        self.assertEqual(names, ["child", "sibling"])
        child = next(c for c in parent.children if c.name == "child")
        self.assertIs(child.parent, parent)
        self.assertLessEqual(child.elapsed, parent.elapsed)

    def test_pool_spans_attach_to_parent(self):
        def work(name):
            with span(name):
                time.sleep(0.005)
            return correlation_id()

        with begin_chain("p") as chain:
            with span("root") as root:
                with TracedThreadPoolExecutor(max_workers=2) as ex:
                    futures = [ex.submit(work, "task-%d" % i) for i in range(3)]
                    ids = [f.result(5) for f in futures]
        self.assertEqual(ids, ["p"] * 3)
        self.assertEqual(chain.roots, [root])
        self.assertEqual(
            sorted(c.name for c in root.children),
            ["task-0", "task-1", "task-2"],
        )

    def test_map_batch_propagates_chain(self):
        def work(x):
            with span("item-%d" % x):
                return correlation_id()

        with begin_chain("batch") as chain:
            with span("batch-span") as root:
                results = map_batch(work, range(6), workers=3)
        self.assertEqual(results, ["batch"] * 6)
        self.assertEqual(chain.roots, [root])
        self.assertEqual(
            sorted(c.name for c in root.children),
            ["item-%d" % i for i in range(6)],
        )

    def test_standalone_span_starts_implicit_chain(self):
        with span("solo"):
            self.assertIsNotNone(correlation_id())
            self.assertIsNotNone(current_span())
        self.assertIsNone(correlation_id())
        self.assertIsNone(current_span())


class TestReport(unittest.TestCase):
    def setUp(self):
        self._saved = get_slow_threshold()
        self.addCleanup(set_slow_threshold, self._saved)

    def test_report_structure_with_slow_marks(self):
        set_slow_threshold(0)  # 任何耗时都算慢
        with begin_chain("r1") as chain:
            with span("root"):
                with span("child"):
                    pass
        lines = chain.report().splitlines()
        self.assertEqual(lines[0], "chain r1:")
        self.assertRegex(lines[1], r"^root \d+\.\dms \[SLOW\]$")
        self.assertRegex(lines[2], r"^  child \d+\.\dms \[SLOW\]$")

    def test_no_slow_mark_under_threshold(self):
        set_slow_threshold(3600)
        with begin_chain("r2") as chain:
            with span("root"):
                with span("child"):
                    pass
        lines = chain.report().splitlines()
        self.assertRegex(lines[1], r"^root \d+\.\dms$")
        self.assertRegex(lines[2], r"^  child \d+\.\dms$")

    def test_span_level_threshold_overrides_global(self):
        set_slow_threshold(3600)
        with begin_chain("r3"):
            with span("fast-limit", slow_threshold=0) as a:
                pass
            with span("slow-limit", slow_threshold=3600) as b:
                pass
        self.assertTrue(a.slow)
        self.assertFalse(b.slow)

    def test_format_report_defaults_to_current_chain(self):
        with begin_chain("r4"):
            with span("s"):
                pass
            text = format_report()
            self.assertIn("chain r4:", text)
            self.assertIn("s ", text)
        self.assertEqual(format_report(), "")

    def test_negative_threshold_rejected(self):
        with self.assertRaises(ValueError):
            set_slow_threshold(-1)


if __name__ == "__main__":
    unittest.main()
