"""FlatSched 改造前行为的锁定测试：这些断言描述的是现状，不是理想。"""

import unittest

from schedx.plan import (
    DuplicateTask,
    FlatSched,
    SchedError,
    UnknownTask,
)


def build(spec):
    """spec 为 (name, dur, deps) 三元组序列，按序登记。"""
    s = FlatSched()
    for name, dur, deps in spec:
        s.add_task(name, dur, deps)
    return s


class TestRegistration(unittest.TestCase):
    def test_add_and_tasks_keep_insertion_order(self):
        s = build([("a", 1, []), ("b", 2, [])])
        self.assertEqual(s.tasks(), ["a", "b"])

    def test_duplicate_task_raises(self):
        s = build([("a", 1, [])])
        with self.assertRaises(DuplicateTask):
            s.add_task("a", 3, [])

    def test_unknown_dependency_raises(self):
        s = FlatSched()
        with self.assertRaises(UnknownTask):
            s.add_task("a", 1, ["missing"])

    def test_empty_name_raises(self):
        s = FlatSched()
        with self.assertRaises(ValueError):
            s.add_task("", 1, [])

    def test_negative_duration_raises(self):
        s = FlatSched()
        with self.assertRaises(ValueError):
            s.add_task("a", -1, [])

    def test_errors_share_base(self):
        self.assertTrue(issubclass(UnknownTask, SchedError))
        self.assertTrue(issubclass(DuplicateTask, SchedError))


class TestReadyTasks(unittest.TestCase):
    def test_no_deps_all_ready(self):
        s = build([("a", 1, []), ("b", 1, []), ("c", 1, [])])
        self.assertEqual(s.ready_tasks(set()), ["a", "b", "c"])

    def test_deps_gate_readiness(self):
        s = build([("a", 1, []), ("b", 1, ["a"]), ("c", 1, ["b"])])
        self.assertEqual(s.ready_tasks(set()), ["a"])
        self.assertEqual(s.ready_tasks({"a"}), ["b"])
        self.assertEqual(s.ready_tasks({"a", "b"}), ["c"])

    def test_done_is_excluded(self):
        s = build([("a", 1, []), ("b", 1, [])])
        self.assertEqual(s.ready_tasks({"a"}), ["b"])

    def test_order_follows_insertion(self):
        s = build([("b", 1, []), ("a", 1, [])])
        self.assertEqual(s.ready_tasks(set()), ["b", "a"])


class TestTopoOrder(unittest.TestCase):
    def test_chain(self):
        s = build([("a", 1, []), ("b", 1, ["a"]), ("c", 1, ["b"])])
        self.assertEqual(s.topo_order(), ["a", "b", "c"])

    def test_diamond_respects_dependencies(self):
        s = build([
            ("root", 1, []),
            ("left", 1, ["root"]),
            ("right", 1, ["root"]),
            ("sink", 1, ["left", "right"]),
        ])
        order = s.topo_order()
        pos = {n: i for i, n in enumerate(order)}
        self.assertLess(pos["root"], pos["left"])
        self.assertLess(pos["root"], pos["right"])
        self.assertLess(pos["left"], pos["sink"])
        self.assertLess(pos["right"], pos["sink"])
        self.assertEqual(sorted(order), ["left", "right", "root", "sink"])

    def test_cycle_raises(self):
        s = build([("b", 1, []), ("a", 1, ["b"])])
        s.add_dep("b", "a")
        with self.assertRaises(SchedError):
            s.topo_order()

    def test_add_dep_rejects_unknown(self):
        s = build([("a", 1, [])])
        with self.assertRaises(UnknownTask):
            s.add_dep("a", "ghost")


class TestSerialTime(unittest.TestCase):
    def test_sum(self):
        s = build([("a", 2, []), ("b", 3, ["a"]), ("c", 4, ["b"])])
        self.assertEqual(s.total_time_serial(), 9)

    def test_empty(self):
        self.assertEqual(FlatSched().total_time_serial(), 0)


class TestCanFinish(unittest.TestCase):
    def test_without_done_only_sources(self):
        s = build([("a", 1, []), ("b", 1, ["a"])])
        self.assertTrue(s.can_finish("a", set()))
        self.assertFalse(s.can_finish("b", set()))

    def test_with_done(self):
        s = build([("a", 1, []), ("b", 1, ["a"])])
        self.assertTrue(s.can_finish("b", {"a"}))

    def test_unknown_raises(self):
        with self.assertRaises(UnknownTask):
            build([("a", 1, [])]).can_finish("z", set())


if __name__ == "__main__":
    unittest.main()
