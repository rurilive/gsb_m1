"""Scheduler 行为基线：真并发、上限、失败/超时、重试、撤销、同序、压序规模。"""

import threading
import time
import unittest

from jobdag import CycleError, JobGraph, RunReport, Scheduler, SequentialRunner


def noop():
    return None


def build_diamond():
    graph = JobGraph()
    graph.add("a", lambda: 1)
    graph.add("b", lambda: 2, deps=["a"])
    graph.add("c", lambda: 3, deps=["a"])
    graph.add("d", lambda: 4, deps=["b", "c"])
    return graph


class TestBasic(unittest.TestCase):

    def test_empty_graph_returns_empty_report(self):
        report = Scheduler(JobGraph(), 8).run()
        self.assertIsInstance(report, RunReport)
        self.assertEqual(report.states, {})
        self.assertTrue(report.ok())

    def test_diamond_all_ok_and_bookkeeping(self):
        graph = build_diamond()
        report = Scheduler(graph, 4).run()
        self.assertEqual(set(report.states), {"a", "b", "c", "d"})
        self.assertTrue(all(s == "ok" for s in report.states.values()))
        self.assertEqual(report.results, {"a": 1, "b": 2, "c": 3, "d": 4})
        self.assertTrue(report.ok())
        self.assertEqual(sorted(report.durations), ["a", "b", "c", "d"])
        self.assertEqual(report.attempts, {"a": 1, "b": 1, "c": 1, "d": 1})

    def test_dependencies_are_respected(self):
        started = []
        lock = threading.Lock()

        def mark(name, delay=0.0):
            def run():
                with lock:
                    started.append(name)
                time.sleep(delay)
                return name
            return run

        graph = JobGraph()
        graph.add("a", mark("a"))
        graph.add("b", mark("b", 0.02), deps=["a"])
        graph.add("c", mark("c", 0.02), deps=["a"])
        graph.add("d", mark("d"), deps=["b", "c"])
        report = Scheduler(graph, 4).run()
        self.assertTrue(all(s == "ok" for s in report.states.values()))
        self.assertLess(started.index("a"), started.index("b"))
        self.assertLess(started.index("a"), started.index("c"))
        self.assertLess(started.index("b"), started.index("d"))
        self.assertLess(started.index("c"), started.index("d"))

    def test_independent_branches_run_in_parallel(self):
        active = 0
        peak = 0
        lock = threading.Lock()

        def slow():
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1

        graph = JobGraph()
        for i in range(8):
            graph.add("j%d" % i, slow)
        report = Scheduler(graph, 4).run()
        self.assertTrue(all(s == "ok" for s in report.states.values()))
        self.assertGreaterEqual(peak, 2)

        start = time.perf_counter()
        Scheduler(graph, 8).run()
        self.assertLess(time.perf_counter() - start, 0.09)

    def test_parallelism_never_exceeds_max(self):
        active = 0
        peak = 0
        lock = threading.Lock()

        def slow():
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1

        graph = JobGraph()
        for i in range(40):
            graph.add("j%d" % i, slow)
        Scheduler(graph, 3).run()
        self.assertEqual(peak, 3)

    def test_invalid_max_parallel_rejected(self):
        graph = JobGraph()
        graph.add("a", noop)
        for bad in (0, -1, 2.0, "2"):
            with self.assertRaises(ValueError):
                Scheduler(graph, bad)


class TestFailureAndTimeout(unittest.TestCase):

    def test_failure_skips_downstream_but_unrelated_branch_runs(self):
        graph = JobGraph()
        graph.add("root", noop)
        graph.add("bad", lambda: (_ for _ in ()).throw(ValueError("boom")),
                  deps=["root"])
        graph.add("child", noop, deps=["bad"])
        graph.add("grand", noop, deps=["child"])
        graph.add("lonely", noop)
        graph.add("lonely2", noop, deps=["lonely"])
        report = Scheduler(graph, 4).run()
        self.assertEqual(report.status("root"), "ok")
        self.assertEqual(report.status("bad"), "failed")
        self.assertEqual(report.status("child"), "skipped")
        self.assertEqual(report.status("grand"), "skipped")
        self.assertEqual(report.status("lonely"), "ok")
        self.assertEqual(report.status("lonely2"), "ok")
        self.assertFalse(report.ok())
        self.assertIsInstance(report.errors["bad"], ValueError)
        self.assertEqual(str(report.errors["bad"]), "boom")
        self.assertNotIn("child", report.results)
        self.assertNotIn("child", report.errors)

    def test_run_returns_report_on_failure_instead_of_raising(self):
        graph = JobGraph()
        graph.add("bad", lambda: 1 / 0)
        report = Scheduler(graph, 1).run()
        self.assertEqual(report.status("bad"), "failed")
        self.assertIsInstance(report.errors["bad"], ZeroDivisionError)

    def test_retries_until_success_and_counts_attempts(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("not yet")
            return "settled"

        graph = JobGraph()
        graph.add("flaky", flaky, retries=3)
        report = Scheduler(graph, 1).run()
        self.assertEqual(report.status("flaky"), "ok")
        self.assertEqual(report.attempts["flaky"], 3)
        self.assertEqual(report.results["flaky"], "settled")

    def test_retry_budget_exhausted_marks_failed(self):
        calls = {"n": 0}

        def always_bad():
            calls["n"] += 1
            raise ValueError("nope")

        graph = JobGraph()
        graph.add("bad", always_bad, retries=2)
        graph.add("down", noop, deps=["bad"])
        report = Scheduler(graph, 2).run()
        self.assertEqual(calls["n"], 3)
        self.assertEqual(report.status("bad"), "failed")
        self.assertEqual(report.attempts["bad"], 3)
        self.assertEqual(report.status("down"), "skipped")

    def test_timeout_marks_node_and_skips_downstream(self):
        graph = JobGraph()
        graph.add("slow", lambda: time.sleep(0.3), timeout=0.05)
        graph.add("after", noop, deps=["slow"])
        graph.add("unrelated", noop)
        start = time.perf_counter()
        report = Scheduler(graph, 2).run()
        elapsed = time.perf_counter() - start
        self.assertEqual(report.status("slow"), "timeout")
        self.assertIsInstance(report.errors["slow"], TimeoutError)
        self.assertEqual(report.status("after"), "skipped")
        self.assertEqual(report.status("unrelated"), "ok")
        self.assertLess(elapsed, 0.2)

    def test_timeout_retries_are_counted(self):
        calls = {"n": 0}

        def always_slow():
            calls["n"] += 1
            time.sleep(0.2)

        graph = JobGraph()
        graph.add("slow", always_slow, timeout=0.03, retries=2)
        report = Scheduler(graph, 1).run()
        self.assertEqual(report.status("slow"), "timeout")
        self.assertEqual(report.attempts["slow"], 3)
        self.assertEqual(calls["n"], 3)

    def test_failure_inside_large_parallel_pool_does_not_hang(self):
        graph = JobGraph()
        for i in range(20):
            graph.add("ok%d" % i, noop)
        graph.add("bad", lambda: 1 / 0)
        for i in range(20):
            graph.add("down%d" % i, noop, deps=["bad"])
        report = Scheduler(graph, 4).run()
        self.assertEqual(len(report.states), 41)
        self.assertEqual(sum(1 for s in report.states.values()
                            if s == "skipped"), 20)


class TestCancel(unittest.TestCase):

    def test_cancel_before_run_marks_all_cancelled(self):
        graph = build_diamond()
        scheduler = Scheduler(graph, 2)
        scheduler.cancel()
        report = scheduler.run()
        self.assertEqual(set(report.states.values()), {"cancelled"})
        self.assertEqual(set(report.attempts.values()), {0})

    def test_cancel_during_run_finishes_in_flight(self):
        graph = JobGraph()
        graph.add("a", lambda: time.sleep(0.12))
        for i in range(12):
            graph.add("tail%d" % i, noop, deps=["a"])
        scheduler = Scheduler(graph, 2)
        holder = {}
        thread = threading.Thread(
            target=lambda: holder.setdefault("report", scheduler.run()))
        thread.start()
        time.sleep(0.03)
        scheduler.cancel()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        report = holder["report"]
        self.assertEqual(report.status("a"), "ok")
        self.assertTrue(all(report.status("tail%d" % i) == "cancelled"
                            for i in range(12)))

    def test_cancel_from_other_thread(self):
        graph = JobGraph()
        graph.add("root", lambda: time.sleep(0.1))
        for i in range(8):
            graph.add("w%d" % i, lambda i=i: time.sleep(0.05),
                      deps=["root"])
        scheduler = Scheduler(graph, 3)
        holder = {}
        thread = threading.Thread(
            target=lambda: holder.setdefault("report", scheduler.run()))
        thread.start()
        timer = threading.Timer(0.03, scheduler.cancel)
        timer.start()
        thread.join(timeout=2)
        timer.join()
        report = holder["report"]
        states = set(report.states.values())
        self.assertTrue(states <= {"ok", "cancelled"})
        self.assertEqual(report.status("root"), "ok")

    def test_cancel_is_idempotent_and_report_is_final(self):
        graph = JobGraph()
        graph.add("a", lambda: time.sleep(0.05))
        graph.add("b", noop, deps=["a"])
        scheduler = Scheduler(graph, 1)
        holder = {}
        thread = threading.Thread(
            target=lambda: holder.setdefault("report", scheduler.run()))
        thread.start()
        scheduler.cancel()
        scheduler.cancel()
        thread.join(timeout=2)
        snapshot = dict(holder["report"].states)
        time.sleep(0.05)
        self.assertEqual(dict(holder["report"].states), snapshot)


class TestOrderingAndScale(unittest.TestCase):

    def test_max_parallel_one_matches_sequential_order(self):
        seq_calls = []
        par_calls = []

        def make(calls, name, delay=0.0):
            def run():
                calls.append(name)
                time.sleep(delay)
                return name
            return run

        graph_seq = JobGraph()
        graph_par = JobGraph()
        for name, deps, delay in (
                ("a", (), 0.0),
                ("b", ("a",), 0.01),
                ("c", ("a",), 0.0),
                ("d", ("b", "c"), 0.0),
                ("e", (), 0.0),
                ("f", ("e",), 0.0)):
            graph_seq.add(name, make(seq_calls, name, delay), deps=deps)
            graph_par.add(name, make(par_calls, name, delay), deps=deps)
        SequentialRunner().run(graph_seq)
        Scheduler(graph_par, 1).run()
        self.assertEqual(par_calls, seq_calls)
        self.assertEqual(par_calls, graph_par.topo_order())

    def test_cycle_error_names_nodes_on_cycle(self):
        graph = JobGraph()
        graph.add("a", noop, deps=["c"])
        graph.add("b", noop, deps=["a"])
        graph.add("c", noop, deps=["b"])
        graph.add("outside", noop)
        with self.assertRaises(CycleError) as ctx:
            graph.topo_order()
        self.assertEqual(set(ctx.exception.nodes), {"a", "b", "c"})
        self.assertNotIn("outside", ctx.exception.nodes)
        message = str(ctx.exception)
        for name in ("a", "b", "c"):
            self.assertIn(name, message)

    def test_self_cycle_reported(self):
        graph = JobGraph()
        graph.add("loop", noop, deps=["loop"])
        with self.assertRaises(CycleError) as ctx:
            graph.topo_order()
        self.assertEqual(ctx.exception.nodes, ("loop",))

    def test_topo_order_huge_chain_within_two_seconds(self):
        graph = JobGraph()
        graph.add("n0", noop)
        for i in range(1, 100000):
            graph.add("n%d" % i, noop, deps=["n%d" % (i - 1)])
        start = time.perf_counter()
        order = graph.topo_order()
        self.assertLess(time.perf_counter() - start, 2.0)
        self.assertEqual(len(order), 100000)
        self.assertEqual(order[0], "n0")
        self.assertEqual(order[-1], "n99999")

    def test_scheduler_huge_empty_graph_within_minute(self):
        graph = JobGraph()
        for i in range(100000):
            graph.add("n%d" % i, noop)
        start = time.perf_counter()
        report = Scheduler(graph, 8).run()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 60.0)
        self.assertEqual(len(report.states), 100000)
        self.assertTrue(report.ok())


if __name__ == "__main__":
    unittest.main()
