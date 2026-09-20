"""JobGraph 行为基线：声明、去重、压序、错误类型。"""

import unittest

from jobdag import CycleError, DuplicateJobError, JobGraph, UnknownDepError
from jobdag import Job


def noop():
    return None


class TestAdd(unittest.TestCase):

    def test_duplicate_name_rejected(self):
        graph = JobGraph()
        graph.add("scan", noop)
        with self.assertRaises(DuplicateJobError):
            graph.add("scan", noop)

    def test_names_keep_declaration_order(self):
        graph = JobGraph()
        for name in ("b", "a", "c"):
            graph.add(name, noop)
        self.assertEqual(graph.names(), ["b", "a", "c"])
        self.assertEqual(len(graph), 3)
        self.assertIn("a", graph)
        self.assertNotIn("z", graph)

    def test_duplicate_deps_are_collapsed(self):
        graph = JobGraph()
        graph.add("a", noop)
        graph.add("b", noop)
        job = graph.add("c", noop, deps=["a", "b", "a", "b"])
        self.assertEqual(job.deps, ("a", "b"))

    def test_dep_may_be_declared_later(self):
        graph = JobGraph()
        graph.add("downstream", noop, deps=["upstream"])
        graph.add("upstream", noop)
        self.assertEqual(graph.topo_order(), ["upstream", "downstream"])

    def test_job_lookup(self):
        graph = JobGraph()
        graph.add("a", noop)
        self.assertIsInstance(graph.job("a"), Job)
        with self.assertRaises(KeyError):
            graph.job("missing")


class TestTopoOrder(unittest.TestCase):

    def test_deps_come_before_dependents(self):
        graph = JobGraph()
        graph.add("a", noop)
        graph.add("b", noop, deps=["a"])
        graph.add("c", noop, deps=["a"])
        graph.add("d", noop, deps=["b", "c"])
        order = graph.topo_order()
        self.assertEqual(sorted(order), ["a", "b", "c", "d"])
        self.assertLess(order.index("a"), order.index("b"))
        self.assertLess(order.index("b"), order.index("d"))
        self.assertLess(order.index("c"), order.index("d"))

    def test_independent_nodes_have_stable_order(self):
        graph = JobGraph()
        for name in ("first", "second", "third"):
            graph.add(name, noop)
        order = graph.topo_order()
        self.assertEqual(sorted(order), ["first", "second", "third"])
        self.assertEqual(order, graph.topo_order())

    def test_empty_graph(self):
        self.assertEqual(JobGraph().topo_order(), [])

    def test_unknown_dep_reported(self):
        graph = JobGraph()
        graph.add("real", noop)
        graph.add("orphan", noop, deps=["real", "ghost"])
        with self.assertRaises(UnknownDepError) as ctx:
            graph.topo_order()
        self.assertIn("ghost", str(ctx.exception))

    def test_cycle_rejected(self):
        graph = JobGraph()
        graph.add("a", noop, deps=["b"])
        graph.add("b", noop, deps=["a"])
        with self.assertRaises(CycleError):
            graph.topo_order()

    def test_order_is_stable_across_calls(self):
        graph = JobGraph()
        graph.add("a", noop)
        graph.add("b", noop)
        graph.add("c", noop, deps=["a", "b"])
        first = graph.topo_order()
        self.assertEqual(first, graph.topo_order())
        self.assertEqual(len(first), 3)

    def test_long_chain_ordered(self):
        graph = JobGraph()
        graph.add("n0", noop)
        for i in range(1, 300):
            graph.add("n%d" % i, noop, deps=["n%d" % (i - 1)])
        order = graph.topo_order()
        self.assertEqual(order, ["n%d" % i for i in range(300)])


if __name__ == "__main__":
    unittest.main()
