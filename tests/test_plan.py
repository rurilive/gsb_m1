"""Executor.plan 的行为测试：只出计划，不执行任何模拟动作。"""

import unittest

import buildplan.executor as executor_mod
from buildplan import (
    Executor,
    GraphError,
    ManifestError,
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

    def test_record_order_and_layer_match_run(self):
        m = parse_manifest(MANIFEST)
        executor = Executor()
        plan = executor.plan(m)
        run = executor.run(m)
        self.assertEqual(
            [(r.layer, r.name) for r in plan.records],
            [(r.layer, r.name) for r in run.records],
        )

    def test_layer_inner_order_follows_declaration(self):
        m = parse_manifest("x:\ny:\nb: x y\na: x\n")
        plan = Executor().plan(m)
        self.assertEqual(plan.layers, [["x", "y"], ["b", "a"]])


class TestPlanDoesNotExecute(unittest.TestCase):
    def test_all_targets_plan_status_zero_cost(self):
        m = parse_manifest(MANIFEST)
        plan = Executor().plan(m)
        self.assertTrue(all(r.status == "plan" for r in plan.records))
        self.assertTrue(all(r.cost_ms == 0 for r in plan.records))
        self.assertEqual(plan.counts, {"plan": len(m)})
        self.assertEqual(plan.total_ms, 0)

    def test_fail_targets_ignored(self):
        m = parse_manifest(MANIFEST)
        plan = Executor(fail_targets={"tools"}).plan(m)
        status = {r.name: r.status for r in plan.records}
        self.assertEqual(set(status.values()), {"plan"})
        self.assertEqual(plan.counts, {"plan": 7})

    def test_no_simulated_action_runs(self):
        # 模拟耗时是"执行动作"的一部分；plan 不应触碰它。
        m = parse_manifest(MANIFEST)

        def boom(name):
            raise AssertionError(f"plan 不应计算模拟耗时: {name}")

        original = executor_mod.target_cost_ms
        executor_mod.target_cost_ms = boom
        try:
            plan = Executor().plan(m)
        finally:
            executor_mod.target_cost_ms = original
        self.assertEqual(len(plan.records), len(m))

    def test_hooks_fire_with_plan_status(self):
        class Recorder(StageVisitor):
            def __init__(self):
                self.events = []

            def on_layer_start(self, index, total, targets):
                self.events.append(("layer_start", index, total, tuple(targets)))

            def on_target_finish(self, name, status, cost_ms):
                self.events.append(("target", name, status, cost_ms))

            def on_layer_finish(self, index):
                self.events.append(("layer_finish", index))

            def on_run_finish(self, counts, total_ms):
                self.events.append(("run_finish", dict(counts), total_ms))

        m = parse_manifest("a:\nb: a\n")
        rec = Recorder()
        Executor(fail_targets={"a"}).plan(m, visitor=rec)
        self.assertEqual(
            rec.events,
            [
                ("layer_start", 1, 2, ("a",)),
                ("target", "a", "plan", 0),
                ("layer_finish", 1),
                ("layer_start", 2, 2, ("b",)),
                ("target", "b", "plan", 0),
                ("layer_finish", 2),
                ("run_finish", {"plan": 2}, 0),
            ],
        )


class TestPlanBadManifest(unittest.TestCase):
    def test_unknown_dep_raises_like_run(self):
        m = parse_manifest("a: ghost\n")
        executor = Executor()
        with self.assertRaises(GraphError) as plan_cm:
            executor.plan(m)
        with self.assertRaises(GraphError) as run_cm:
            executor.run(m)
        self.assertEqual(str(plan_cm.exception), str(run_cm.exception))

    def test_cycle_raises_like_run(self):
        m = parse_manifest("a: b\nb: c\nc: a\n")
        executor = Executor()
        with self.assertRaises(GraphError) as plan_cm:
            executor.plan(m)
        with self.assertRaises(GraphError) as run_cm:
            executor.run(m)
        self.assertEqual(str(plan_cm.exception), str(run_cm.exception))

    def test_self_cycle_raises(self):
        m = parse_manifest("a: a\n")
        with self.assertRaises(GraphError):
            Executor().plan(m)

    def test_manifest_errors_unchanged(self):
        with self.assertRaises(ManifestError):
            parse_manifest("a:\n没有冒号\n")
        with self.assertRaises(ManifestError):
            parse_manifest("a:\nb: a\na:\n")
        with self.assertRaises(ManifestError):
            parse_manifest("# 只有注释\n")


class TestPlanText(unittest.TestCase):
    def test_plan_text_golden(self):
        m = parse_manifest(MANIFEST)
        plan = Executor(fail_targets={"tools"}).plan(m)
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

    def test_plan_header_has_no_counts_or_total(self):
        m = parse_manifest(MANIFEST)
        first_line = Executor().plan(m).text.splitlines()[0]
        self.assertNotIn("ok=", first_line)
        self.assertNotIn("total", first_line)
        self.assertIn("7 target(s) in 5 layer(s)", first_line)

    def test_plan_body_matches_run_layout(self):
        # 层标题行与 run 完全一致，目标行只是去掉耗时列、状态换 plan。
        m = parse_manifest(MANIFEST)
        executor = Executor()
        plan_lines = executor.plan(m).text.splitlines()[1:]
        run_lines = executor.run(m).text.splitlines()[1:]
        plan_layers = [l for l in plan_lines if l.startswith("[")]
        run_layers = [l for l in run_lines if l.startswith("[")]
        self.assertEqual(plan_layers, run_layers)
        plan_targets = [l for l in plan_lines if not l.startswith("[")]
        run_targets = [l for l in run_lines if not l.startswith("[")]
        self.assertEqual(len(plan_targets), len(run_targets))
        for plan_line, run_line in zip(plan_targets, run_targets):
            self.assertEqual(plan_line, "  plan   " + run_line.split()[-2])


if __name__ == "__main__":
    unittest.main()
