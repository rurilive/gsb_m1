"""plan 模式的行为测试：只出执行计划，不执行任何模拟动作。"""

import unittest

from buildplan import (
    Executor,
    GraphError,
    PlanReport,
    StageVisitor,
    layer_targets,
    parse_manifest,
)

MANIFEST = """\
# demo 项目的构建清单
base:
core: base
net: base
server: core net
tools: core
tests: server tools
docs: tests
"""


class TestPlanLayering(unittest.TestCase):
    def test_layers_match_run(self):
        m = parse_manifest(MANIFEST)
        executor = Executor(fail_targets={"tools"})
        plan = executor.plan(m)
        run = executor.run(m)
        self.assertEqual(plan.layers, run.layers)
        self.assertEqual(plan.layers, layer_targets(m))

    def test_record_order_matches_run(self):
        m = parse_manifest(MANIFEST)
        executor = Executor()
        plan = executor.plan(m)
        run = executor.run(m)
        self.assertEqual(
            [(r.layer, r.name) for r in plan.records],
            [(r.layer, r.name) for r in run.records],
        )


class TestPlanDoesNotExecute(unittest.TestCase):
    def test_all_records_plan_status_zero_cost(self):
        m = parse_manifest(MANIFEST)
        plan = Executor(fail_targets={"tools"}).plan(m)
        self.assertTrue(all(r.status == "plan" for r in plan.records))
        self.assertTrue(all(r.cost_ms == 0 for r in plan.records))
        self.assertEqual(plan.total_ms, 0)

    def test_ignores_fail_targets(self):
        m = parse_manifest(MANIFEST)
        plan = Executor(fail_targets={"tools", "base"}).plan(m)
        self.assertEqual(plan.counts["plan"], len(m))
        self.assertEqual(plan.counts["failed"], 0)
        self.assertEqual(plan.counts["skip"], 0)

    def test_hooks_observe_plan_progression(self):
        events = []

        class Recorder(StageVisitor):
            def on_layer_start(self, index, total, targets):
                events.append(("layer_start", index, total, tuple(targets)))

            def on_target_finish(self, name, status, cost_ms):
                events.append(("target", name, status, cost_ms))

            def on_layer_finish(self, index):
                events.append(("layer_finish", index))

            def on_run_finish(self, counts, total_ms):
                events.append(("run_finish", dict(counts), total_ms))

        m = parse_manifest("a:\nb: a\n")
        Executor(fail_targets={"a"}).plan(m, visitor=Recorder())
        self.assertEqual(
            events,
            [
                ("layer_start", 1, 2, ("a",)),
                ("target", "a", "plan", 0),
                ("layer_finish", 1),
                ("layer_start", 2, 2, ("b",)),
                ("target", "b", "plan", 0),
                ("layer_finish", 2),
                ("run_finish", {"ok": 0, "skip": 0, "failed": 0, "plan": 2}, 0),
            ],
        )


class TestPlanErrors(unittest.TestCase):
    def test_unknown_dep_raises_like_run(self):
        m = parse_manifest("a: ghost\n")
        executor = Executor()
        with self.assertRaises(GraphError) as plan_cm:
            executor.plan(m)
        with self.assertRaises(GraphError) as run_cm:
            executor.run(m)
        self.assertEqual(str(plan_cm.exception), str(run_cm.exception))

    def test_cycle_raises_like_run(self):
        m = parse_manifest("a: b\nb: a\n")
        executor = Executor()
        with self.assertRaises(GraphError) as plan_cm:
            executor.plan(m)
        with self.assertRaises(GraphError) as run_cm:
            executor.run(m)
        self.assertEqual(str(plan_cm.exception), str(run_cm.exception))


class TestPlanText(unittest.TestCase):
    def test_text_golden(self):
        m = parse_manifest(MANIFEST)
        plan = Executor(fail_targets={"tools"}).plan(m)
        self.assertIsInstance(plan, PlanReport)
        self.assertEqual(
            plan.text,
            "plan: 7 target(s) in 5 layer(s)\n"
            "[1/5] base\n"
            "  plan   base\n"
            "[2/5] core net\n"
            "  plan   core\n"
            "  plan   net\n"
            "[3/5] server tools\n"
            "  plan   server\n"
            "  plan   tools\n"
            "[4/5] tests\n"
            "  plan   tests\n"
            "[5/5] docs\n"
            "  plan   docs\n",
        )

    def test_layer_lines_match_run_text(self):
        m = parse_manifest(MANIFEST)
        executor = Executor()
        plan_lines = [
            line for line in executor.plan(m).text.splitlines()
            if line.startswith("[")
        ]
        run_lines = [
            line for line in executor.run(m).text.splitlines()
            if line.startswith("[")
        ]
        self.assertEqual(plan_lines, run_lines)


if __name__ == "__main__":
    unittest.main()
