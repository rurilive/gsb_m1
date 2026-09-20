"""tracing 行为测试：并发隔离、嵌套计时、报告结构（确定性，不依赖时序）。"""

import threading
import time
import unittest

from tracectx import (
    ItemFailure,
    RUNNING_MARKER,
    SLOW_MARKER,
    TracedThreadPoolExecutor,
    TracedThread,
    async_call,
    current_span,
    current_trace,
    current_trace_id,
    map_batch,
    new_trace_id,
    run_detached,
    span,
    start_trace,
    wrap,
)


class TestCorrelationId(unittest.TestCase):
    def test_new_trace_id_is_unique_nonempty(self):
        ids = {new_trace_id() for _ in range(20)}
        self.assertNotIn("", ids)
        self.assertEqual(len(ids), 20)

    def test_trace_gets_id_and_contextvar(self):
        with start_trace("job") as trace:
            self.assertEqual(current_trace_id(), trace.trace_id)
            self.assertIs(current_trace(), trace)
        self.assertIsNone(current_trace_id())

    def test_explicit_id_used_verbatim(self):
        with start_trace("job", trace_id="fixed-id") as trace:
            self.assertEqual(trace.trace_id, "fixed-id")
            self.assertEqual(current_trace_id(), "fixed-id")

    def test_no_trace_outside_context(self):
        self.assertIsNone(current_trace())
        self.assertIsNone(current_trace_id())


class TestThreadPropagation(unittest.TestCase):
    def test_traced_thread_carries_id(self):
        seen = []
        ready = threading.Event()

        with start_trace("job") as trace:
            def work():
                seen.append(current_trace_id())
                ready.set()

            t = TracedThread(target=work)
            t.start()
            self.assertTrue(ready.wait(5))
            t.join(5)

        self.assertEqual(seen, [trace.trace_id])

    def test_child_span_in_thread_attaches_to_parent(self):
        with start_trace("job") as trace:
            def work():
                with span("in-thread"):
                    time.sleep(0.01)

            t = TracedThread(target=work)
            t.start()
            t.join(5)

        names = [c.name for c in trace.root.children]
        self.assertIn("in-thread", names)

    def test_concurrent_traced_threads_isolated(self):
        n = 8
        barrier = threading.Barrier(n)
        results = {}
        lock = threading.Lock()
        traces = []

        def worker(i, trace_box):
            barrier.wait(5)
            with start_trace("trace-%d" % i) as trace:
                trace_box.append(trace)
                with span("work:%d" % i):
                    got = current_trace_id()
                    time.sleep(0.01)
                with lock:
                    results[i] = got

        threads = []
        for i in range(n):
            trace_box = []
            traces.append(trace_box)
            t = TracedThread(target=worker, args=(i, trace_box))
            t.start()
            threads.append(t)
        for t in threads:
            t.join(5)

        traces = [box[0] for box in traces]

        for i, trace in enumerate(traces):
            self.assertEqual(results[i], trace.trace_id)
            names = [c.name for c in trace.root.children]
            self.assertEqual(names, ["work:%d" % i])

    def test_concurrent_map_batch_chains_isolated(self):
        n_chains = 3
        per_chain = 6
        barrier = threading.Barrier(n_chains)
        ids = {}
        lock = threading.Lock()

        def process(x):
            barrier.wait(5)
            with span("item:%s" % x):
                tid = current_trace_id()
                time.sleep(0.01)
            with lock:
                ids[x] = tid
            return x

        def chain(prefix):
            with start_trace("chain:" + prefix) as trace:
                items = ["%s-%d" % (prefix, i) for i in range(per_chain)]
                map_batch(process, items, workers=4)
            return trace

        traces = []
        result_lock = threading.Lock()

        def chain_worker(prefix):
            trace = chain(prefix)
            with result_lock:
                traces.append(trace)

        outer = [TracedThread(target=chain_worker, args=(p,))
                 for p in ("a", "b", "c")]
        for t in outer:
            t.start()
        for t in outer:
            t.join(5)

        by_prefix = {trace.name.split(":", 1)[1]: trace for trace in traces}
        self.assertEqual(set(by_prefix), {"a", "b", "c"})

        for prefix, trace in by_prefix.items():
            child_names = sorted(c.name for c in trace.root.children)
            self.assertEqual(
                child_names,
                sorted("item:%s-%d" % (prefix, i) for i in range(per_chain)),
            )
            for i in range(per_chain):
                key = "%s-%d" % (prefix, i)
                self.assertEqual(ids[key], trace.trace_id)

    def test_pool_isolates_concurrent_traces(self):
        n = 4
        barrier = threading.Barrier(n)
        captured = [None] * n
        child_names = [None] * n

        def job(i):
            barrier.wait(5)
            with start_trace("pool-trace-%d" % i) as trace:
                with span("pool-work:%d" % i):
                    captured[i] = current_trace_id()
                    time.sleep(0.01)
                child_names[i] = [c.name for c in trace.root.children]

        pool = TracedThreadPoolExecutor(max_workers=n)
        try:
            futures = []
            for i in range(n):
                futures.append(pool.submit(job, i))
            for future in futures:
                future.result(5)
        finally:
            pool.shutdown()

        # 每条链路的 id 只在自己的工作线程上下文里出现，互不相同
        self.assertEqual(len(set(captured)), n)
        for i in range(n):
            self.assertEqual(child_names[i], ["pool-work:%d" % i])

    def test_pool_map_propagates_context(self):
        with start_trace("pool-map") as trace:
            pool = TracedThreadPoolExecutor(max_workers=3)
            try:
                seen = list(pool.map(lambda x: current_trace_id(), [1, 2, 3]))
            finally:
                pool.shutdown()
        self.assertEqual(seen, [trace.trace_id] * 3)

    def test_plain_thread_does_not_leak_id(self):
        with start_trace("job"):
            seen = []
            done = threading.Event()

            def work():
                seen.append(current_trace_id())
                done.set()

            t = threading.Thread(target=work)
            t.start()
            done.wait(5)
            t.join(5)

        self.assertEqual(seen, [None])


class TestNestedSpans(unittest.TestCase):
    def test_spans_nest_by_context(self):
        with start_trace("job") as trace:
            with span("outer") as outer:
                with span("inner") as inner:
                    self.assertIs(current_span(), inner)
                self.assertIs(current_span(), outer)

        self.assertIs(outer.parent, trace.root)
        self.assertIs(inner.parent, outer)
        self.assertEqual([c.name for c in trace.root.children], ["outer"])
        self.assertEqual([c.name for c in outer.children], ["inner"])

    def test_monotonic_timing_ordering(self):
        with start_trace("job") as trace:
            with span("outer") as outer:
                time.sleep(0.02)
                with span("inner") as inner:
                    time.sleep(0.02)

        self.assertGreaterEqual(inner.duration, 0.015)
        self.assertGreaterEqual(outer.duration, inner.duration)
        self.assertGreaterEqual(trace.root.duration, outer.duration)

    def test_slow_marker_uses_threshold(self):
        with start_trace("job", slow_threshold=0.02) as trace:
            with span("fast"):
                time.sleep(0.005)
            with span("slow"):
                time.sleep(0.04)

        fast = trace.root.children[0]
        slow = trace.root.children[1]
        self.assertFalse(fast.slow)
        self.assertTrue(slow.slow)

    def test_span_level_threshold_overrides_trace(self):
        with start_trace("job", slow_threshold=10) as trace:
            with span("still-slow", slow_threshold=0.01):
                time.sleep(0.03)

        self.assertTrue(trace.root.children[0].slow)

    def test_zero_threshold_marks_everything(self):
        with start_trace("job", slow_threshold=0) as trace:
            with span("any"):
                pass

        self.assertTrue(trace.root.slow)
        self.assertTrue(trace.root.children[0].slow)

    def test_no_threshold_never_slow(self):
        with start_trace("job") as trace:
            with span("work"):
                time.sleep(0.01)

        self.assertFalse(trace.root.slow)
        self.assertFalse(trace.root.children[0].slow)

    def test_null_span_outside_trace_is_noop(self):
        null = current_span()
        with span("ignored") as entered:
            self.assertIs(entered, null)
            self.assertEqual(entered.elapsed(), 0.0)
        self.assertIsNone(current_trace_id())

    def test_running_span_elapsed_and_marker(self):
        with start_trace("job") as trace:
            child = trace.new_span("open")
            child.begin()
            time.sleep(0.01)
            self.assertGreaterEqual(child.elapsed(), 0.005)
            self.assertIn(RUNNING_MARKER, trace.report())
            child.finish()

        self.assertGreaterEqual(child.duration, 0.005)

    def test_close_idempotent_and_finishes_tree(self):
        with start_trace("job") as trace:
            with span("child"):
                pass
            trace.close()  # 退出前提前收尾
            trace.close()  # 幂等
            self.assertIsNotNone(trace.root.duration)
            self.assertIsNotNone(trace.root.children[0].duration)
        self.assertIsNone(current_trace_id())


class TestReport(unittest.TestCase):
    def _lines(self, trace):
        return trace.report().splitlines()

    def test_header_has_name_and_id(self):
        with start_trace("job-x") as trace:
            pass
        report = trace.report()
        self.assertTrue(report.startswith("trace job-x "))
        self.assertIn(trace.trace_id, report)

    def test_tree_indentation_follows_nesting(self):
        with start_trace("job") as trace:
            with span("alpha"):
                with span("alpha-one"):
                    pass
                with span("alpha-two"):
                    pass
            with span("beta"):
                pass

        body = self._lines(trace)[1:]  # 去掉 header，首行是根 span

        def parsed(line):
            stripped = line.lstrip(" ")
            return len(line) - len(stripped), stripped.split(" ", 1)[0]

        self.assertEqual(
            [parsed(ln) for ln in body],
            [
                (0, "job"),
                (2, "alpha"),
                (4, "alpha-one"),
                (4, "alpha-two"),
                (2, "beta"),
            ],
        )

    def test_every_line_has_duration(self):
        with start_trace("job") as trace:
            with span("a"):
                with span("a1"):
                    time.sleep(0.005)

        for line in self._lines(trace)[1:]:
            self.assertRegex(line, r"\d+\.\d{3}s$")

    def test_slow_marker_in_report(self):
        with start_trace("job", slow_threshold=0.01) as trace:
            with span("slow-span"):
                time.sleep(0.03)

        lines = self._lines(trace)
        slow_lines = [ln for ln in lines if SLOW_MARKER in ln]
        self.assertTrue(any("slow-span" in ln for ln in slow_lines))
        self.assertTrue(any(ln.lstrip().startswith("job") for ln in slow_lines))
        for line in slow_lines:
            self.assertIn("[" + SLOW_MARKER + "]", line)

    def test_report_lists_each_span_once(self):
        with start_trace("job") as trace:
            with span("alpha"):
                with span("alpha-one"):
                    pass
            with span("beta"):
                pass

        body = self._lines(trace)[1:]

        def name_of(line):
            return line.lstrip(" ").split(" ", 1)[0]

        names = [name_of(ln) for ln in body]
        self.assertEqual(names, ["job", "alpha", "alpha-one", "beta"])


class TestWrap(unittest.TestCase):
    def test_wrap_carries_context_to_plain_thread(self):
        seen = []
        done = threading.Event()

        def work():
            seen.append(current_trace_id())
            done.set()

        with start_trace("job") as trace:
            wrapped = wrap(work)
            t = threading.Thread(target=wrapped)
            t.start()
            done.wait(5)
            t.join(5)

        self.assertEqual(seen, [trace.trace_id])

    def test_wrapped_span_attaches_to_outer_tree(self):
        with start_trace("outer") as trace:
            captured = {}

            def remote():
                with span("inner"):
                    captured["id"] = current_trace_id()

            ctx_thread = threading.Thread(target=wrap(remote))
            ctx_thread.start()
            ctx_thread.join(5)

        self.assertEqual(captured["id"], trace.trace_id)
        self.assertIn("inner", [c.name for c in trace.root.children])


class TestExecutionIntegration(unittest.TestCase):
    def test_map_batch_propagates_id_and_spans(self):
        with start_trace("batch", slow_threshold=0.01) as trace:
            def fn(x):
                with span("item:%d" % x):
                    time.sleep(0.02 if x == 2 else 0.002)
                    return current_trace_id()

            results = map_batch(fn, [1, 2, 3], workers=3)

        self.assertEqual(set(results), {trace.trace_id})
        names = sorted(c.name for c in trace.root.children)
        self.assertEqual(names, ["item:1", "item:2", "item:3"])
        slow = {c.name: c.slow for c in trace.root.children}
        self.assertTrue(slow["item:2"])
        self.assertFalse(slow["item:1"])

    def test_run_detached_propagates_span(self):
        with start_trace("job") as trace:
            def work():
                with span("detached-work"):
                    return current_trace_id()

            tid = run_detached(work)

        self.assertEqual(tid, trace.trace_id)
        self.assertIn("detached-work", [c.name for c in trace.root.children])

    def test_async_callbacks_run_in_trace_context(self):
        done = threading.Event()
        captured = {}

        def on_done(value):
            captured["value"] = value
            captured["id"] = current_trace_id()
            with span("on-done"):
                time.sleep(0.005)
            done.set()

        with start_trace("job") as trace:
            t = async_call(lambda: 42, on_done=on_done)
            self.assertTrue(done.wait(5))
            t.join(5)

        self.assertEqual(captured["value"], 42)
        self.assertEqual(captured["id"], trace.trace_id)
        names = [c.name for c in trace.root.children]
        self.assertIn("on-done", names)

    def test_failed_item_still_records_span(self):
        with start_trace("batch") as trace:
            def fn(x):
                with span("item:%d" % x):
                    if x == 2:
                        raise ValueError("bad")
                    return x

            results = map_batch(fn, [1, 2], workers=2)

        self.assertIsInstance(results[1], ItemFailure)
        names = sorted(c.name for c in trace.root.children)
        self.assertEqual(names, ["item:1", "item:2"])


if __name__ == "__main__":
    unittest.main()
