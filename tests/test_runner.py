"""SequentialRunner 行为基线：执行序、记账、失败即中断。"""

import time
import unittest

from jobdag import JobGraph, RunReport, SequentialRunner


class TestSequentialRunner(unittest.TestCase):

    def test_runs_each_node_once_in_order(self):
        calls = []

        def make(name):
            def run():
                calls.append(name)
                return name.upper()
            return run

        graph = JobGraph()
        graph.add("a", make("a"))
        graph.add("b", make("b"), deps=["a"])
        graph.add("c", make("c"), deps=["a"])
        graph.add("d", make("d"), deps=["b", "c"])
        report = SequentialRunner().run(graph)
        self.assertEqual(sorted(calls), ["a", "b", "c", "d"])
        self.assertLess(calls.index("a"), calls.index("b"))
        self.assertLess(calls.index("b"), calls.index("d"))
        self.assertLess(calls.index("c"), calls.index("d"))

    def test_report_bookkeeping(self):
        graph = JobGraph()
        graph.add("plain", lambda: 7)
        graph.add("none", lambda: None, deps=["plain"])
        graph.add("empty", lambda: "", deps=["plain"])
        report = SequentialRunner().run(graph)
        self.assertIsInstance(report, RunReport)
        self.assertEqual(report.status("plain"), "ok")
        self.assertEqual(report.results["plain"], 7)
        self.assertIn("none", report.results)
        self.assertIsNone(report.results["none"])
        self.assertEqual(report.results["empty"], "")
        self.assertTrue(report.ok())
        self.assertEqual(sorted(report.durations), ["empty", "none", "plain"])
        self.assertEqual(report.errors, {})

    def test_durations_are_measured_per_node(self):
        graph = JobGraph()
        graph.add("slow", lambda: time.sleep(0.02))
        report = SequentialRunner().run(graph)
        self.assertGreaterEqual(report.durations["slow"], 0.015)

    def test_failure_stops_remaining_nodes(self):
        calls = []

        def boom():
            calls.append("boom")
            raise ValueError("bad row")

        graph = JobGraph()
        graph.add("first", lambda: calls.append("first"))
        graph.add("boom", boom, deps=["first"])
        graph.add("after", lambda: calls.append("after"), deps=["boom"])
        with self.assertRaises(ValueError):
            SequentialRunner().run(graph)
        self.assertEqual(calls, ["first", "boom"])

    def test_empty_graph_runs_clean(self):
        report = SequentialRunner().run(JobGraph())
        self.assertEqual(report.states, {})
        self.assertTrue(report.ok())

    def test_shared_callable_serves_several_nodes(self):
        seen = []

        def shared():
            seen.append(1)
            return len(seen)

        graph = JobGraph()
        graph.add("one", shared)
        graph.add("two", shared, deps=["one"])
        report = SequentialRunner().run(graph)
        self.assertEqual(report.results, {"one": 1, "two": 2})


if __name__ == "__main__":
    unittest.main()
