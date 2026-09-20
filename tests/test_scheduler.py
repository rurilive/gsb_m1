"""Scheduler 行为：真并行、并发上限、失败跳过、重试超时、跨线程撤销。"""

import threading
import time
import unittest

from jobdag import CycleError, JobGraph, RunReport, Scheduler, SequentialRunner


def noop():
    return None


class TestParallelExecution(unittest.TestCase):

    def test_independent_nodes_run_in_parallel(self):
        graph = JobGraph()
        for i in range(4):
            graph.add("n%d" % i, lambda: time.sleep(0.1))
        start = time.perf_counter()
        report = Scheduler(graph, max_parallel=4).run()
        elapsed = time.perf_counter() - start
        self.assertTrue(report.ok())
        self.assertLess(elapsed, 0.3)

    def test_concurrency_never_exceeds_limit(self):
        lock = threading.Lock()
        current = [0]
        peak = [0]

        def work():
            with lock:
                current[0] += 1
                peak[0] = max(peak[0], current[0])
            time.sleep(0.02)
            with lock:
                current[0] -= 1

        graph = JobGraph()
        for i in range(12):
            graph.add("n%d" % i, work)
        report = Scheduler(graph, max_parallel=3).run()
        self.assertTrue(report.ok())
        self.assertLessEqual(peak[0], 3)
        self.assertGreaterEqual(peak[0], 2)

    def test_max_parallel_one_matches_sequential_order(self):
        calls = []

        def make(name):
            def run():
                calls.append(name)
                return name
            return run

        graph = JobGraph()
        graph.add("a", make("a"))
        graph.add("b", make("b"), deps=["a"])
        graph.add("c", make("c"))
        graph.add("d", make("d"), deps=["b", "c"])
        Scheduler(graph, max_parallel=1).run()
        scheduled = list(calls)
        del calls[:]
        SequentialRunner().run(graph)
        self.assertEqual(scheduled, calls)
        self.assertEqual(scheduled, graph.topo_order())

    def test_invalid_max_parallel_rejected(self):
        with self.assertRaises(ValueError):
            Scheduler(JobGraph(), max_parallel=0)

    def test_empty_graph_runs_clean(self):
        report = Scheduler(JobGraph(), max_parallel=8).run()
        self.assertIsInstance(report, RunReport)
        self.assertEqual(report.states, {})
        self.assertTrue(report.ok())


class TestFailureAndSkip(unittest.TestCase):

    def test_failure_skips_downstream_unrelated_branch_runs(self):
        def boom():
            raise ValueError("bad row")

        graph = JobGraph()
        graph.add("extract", lambda: 1)
        graph.add("transform", boom, deps=["extract"])
        graph.add("load", lambda: 3, deps=["transform"])
        graph.add("publish", lambda: 4, deps=["load"])
        graph.add("audit", lambda: 5, deps=["extract"])
        report = Scheduler(graph, max_parallel=2).run()
        self.assertEqual(report.status("extract"), "ok")
        self.assertEqual(report.status("transform"), "failed")
        self.assertIsInstance(report.errors["transform"], ValueError)
        self.assertEqual(report.status("load"), "skipped")
        self.assertEqual(report.status("publish"), "skipped")
        self.assertEqual(report.status("audit"), "ok")
        self.assertEqual(report.results["audit"], 5)
        self.assertFalse(report.ok())

    def test_run_returns_report_instead_of_raising(self):
        graph = JobGraph()
        graph.add("bad", lambda: 1 / 0)
        report = Scheduler(graph, max_parallel=1).run()
        self.assertEqual(report.status("bad"), "failed")
        self.assertIsInstance(report.errors["bad"], ZeroDivisionError)


class TestRetryAndTimeout(unittest.TestCase):

    def test_retry_until_success(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ValueError("not yet")
            return "ok"

        graph = JobGraph()
        graph.add("flaky", flaky, retries=2)
        report = Scheduler(graph, max_parallel=1).run()
        self.assertEqual(report.status("flaky"), "ok")
        self.assertEqual(report.results["flaky"], "ok")
        self.assertEqual(report.attempts["flaky"], 3)

    def test_retry_exhausted_marks_failed(self):
        graph = JobGraph()
        graph.add("bad", lambda: 1 / 0, retries=2)
        graph.add("downstream", noop, deps=["bad"])
        report = Scheduler(graph, max_parallel=1).run()
        self.assertEqual(report.status("bad"), "failed")
        self.assertEqual(report.attempts["bad"], 3)
        self.assertEqual(report.status("downstream"), "skipped")

    def test_timeout_marks_failed_and_skips_downstream(self):
        graph = JobGraph()
        graph.add("slow", lambda: time.sleep(0.3), timeout=0.05)
        graph.add("child", noop, deps=["slow"])
        graph.add("free", lambda: "fine")
        report = Scheduler(graph, max_parallel=2).run()
        self.assertEqual(report.status("slow"), "failed")
        self.assertIsInstance(report.errors["slow"], TimeoutError)
        self.assertEqual(report.status("child"), "skipped")
        self.assertEqual(report.status("free"), "ok")

    def test_invalid_retry_and_timeout_rejected(self):
        graph = JobGraph()
        with self.assertRaises(ValueError):
            graph.add("neg", noop, retries=-1)
        with self.assertRaises(ValueError):
            graph.add("zero", noop, timeout=0)


class TestCancel(unittest.TestCase):

    def test_cancel_marks_unstarted_nodes(self):
        started = threading.Event()
        release = threading.Event()

        def slow():
            started.set()
            release.wait(2)
            return "done"

        graph = JobGraph()
        graph.add("slow", slow)
        graph.add("next", noop, deps=["slow"])
        graph.add("tail", noop, deps=["next"])
        scheduler = Scheduler(graph, max_parallel=2)
        outcome = []
        worker = threading.Thread(
            target=lambda: outcome.append(scheduler.run()))
        worker.start()
        self.assertTrue(started.wait(2))
        scheduler.cancel()
        release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        report = outcome[0]
        self.assertEqual(report.status("slow"), "ok")
        self.assertEqual(report.results["slow"], "done")
        self.assertEqual(report.status("next"), "cancelled")
        self.assertEqual(report.status("tail"), "cancelled")
        self.assertFalse(report.ok())

    def test_report_is_final_after_cancel(self):
        graph = JobGraph()
        graph.add("quick", noop)
        graph.add("later", noop, deps=["quick"])
        scheduler = Scheduler(graph, max_parallel=1)
        scheduler.cancel()
        report = scheduler.run()
        snapshot = dict(report.states)
        time.sleep(0.05)
        self.assertEqual(report.states, snapshot)
        self.assertEqual(set(snapshot), {"quick", "later"})
        self.assertTrue(all(state == "cancelled" for state in snapshot.values()))


class TestCycleMessage(unittest.TestCase):

    def test_cycle_error_names_nodes_on_cycle(self):
        graph = JobGraph()
        graph.add("alpha", noop, deps=["beta"])
        graph.add("beta", noop, deps=["gamma"])
        graph.add("gamma", noop, deps=["alpha"])
        with self.assertRaises(CycleError) as ctx:
            graph.topo_order()
        message = str(ctx.exception)
        for name in ("alpha", "beta", "gamma"):
            self.assertIn(name, message)


class TestScale(unittest.TestCase):

    def test_long_chain_topo_without_recursion_error(self):
        count = 100000
        graph = JobGraph()
        graph.add("n0", noop)
        for i in range(1, count):
            graph.add("n%d" % i, noop, deps=["n%d" % (i - 1)])
        start = time.perf_counter()
        order = graph.topo_order()
        elapsed = time.perf_counter() - start
        self.assertEqual(len(order), count)
        self.assertEqual(order[0], "n0")
        self.assertEqual(order[-1], "n%d" % (count - 1))
        self.assertLess(elapsed, 2.0)

    def test_large_empty_graph_finishes_in_time(self):
        count = 100000
        graph = JobGraph()
        for i in range(count):
            graph.add("n%d" % i, noop)
        start = time.perf_counter()
        report = Scheduler(graph, max_parallel=8).run()
        elapsed = time.perf_counter() - start
        self.assertTrue(report.ok())
        self.assertEqual(len(report.states), count)
        self.assertLess(elapsed, 60.0)


if __name__ == "__main__":
    unittest.main()
