"""buildplan 现有行为的锁定测试。"""

import unittest

from buildplan import (
    Executor,
    GraphError,
    ManifestError,
    StageVisitor,
    layer_targets,
    parse_manifest,
    target_cost_ms,
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


class TestParse(unittest.TestCase):
    def test_parse_basic(self):
        m = parse_manifest("a: b c\nb:\nc:\n")
        self.assertEqual(m.order, ["a", "b", "c"])
        self.assertEqual(m.targets["a"].deps, ("b", "c"))
        self.assertEqual(m.targets["b"].deps, ())

    def test_comments_and_blank_lines(self):
        m = parse_manifest("# 头注释\n\na: b  # 行尾注释\nb:\n")
        self.assertEqual(m.order, ["a", "b"])

    def test_declaration_order_kept(self):
        m = parse_manifest("z:\nm:\na:\n")
        self.assertEqual(m.order, ["z", "m", "a"])

    def test_no_colon_raises(self):
        with self.assertRaises(ManifestError) as cm:
            parse_manifest("a:\n居然没有冒号\n")
        self.assertIn("第 2 行", str(cm.exception))

    def test_duplicate_target_raises(self):
        with self.assertRaises(ManifestError) as cm:
            parse_manifest("a:\nb: a\na:\n")
        self.assertIn("a", str(cm.exception))

    def test_empty_manifest_raises(self):
        with self.assertRaises(ManifestError):
            parse_manifest("# 只有注释\n\n")

    def test_bad_target_name_raises(self):
        with self.assertRaises(ManifestError):
            parse_manifest("a b: c\n")

    def test_contains_and_len(self):
        m = parse_manifest("a:\nb:\n")
        self.assertIn("a", m)
        self.assertNotIn("c", m)
        self.assertEqual(len(m), 2)


class TestLayering(unittest.TestCase):
    def test_chain(self):
        m = parse_manifest("c: b\nb: a\na:\n")
        self.assertEqual(layer_targets(m), [["a"], ["b"], ["c"]])

    def test_diamond(self):
        m = parse_manifest("a:\nb: a\nc: a\nd: b c\n")
        self.assertEqual(layer_targets(m), [["a"], ["b", "c"], ["d"]])

    def test_layer_inner_order_follows_declaration(self):
        m = parse_manifest("x:\ny:\nb: x y\na: x\n")
        self.assertEqual(layer_targets(m), [["x", "y"], ["b", "a"]])

    def test_unknown_dep_raises(self):
        m = parse_manifest("a: ghost\n")
        with self.assertRaises(GraphError) as cm:
            layer_targets(m)
        self.assertIn("ghost", str(cm.exception))
        self.assertIn("a", str(cm.exception))

    def test_cycle_raises(self):
        m = parse_manifest("a: b\nb: c\nc: a\n")
        with self.assertRaises(GraphError) as cm:
            layer_targets(m)
        self.assertIn("成环", str(cm.exception))

    def test_self_cycle_raises(self):
        m = parse_manifest("a: a\n")
        with self.assertRaises(GraphError):
            layer_targets(m)

    def test_demo_manifest_layers(self):
        m = parse_manifest(MANIFEST)
        self.assertEqual(
            layer_targets(m),
            [["base"], ["core", "net"], ["server", "tools"], ["tests"], ["docs"]],
        )


class TestExecute(unittest.TestCase):
    def test_cost_deterministic(self):
        self.assertEqual(target_cost_ms("base"), 4)
        self.assertEqual(target_cost_ms("core"), 9)
        self.assertEqual(target_cost_ms("net"), 1)
        self.assertEqual(target_cost_ms("base"), target_cost_ms("base"))

    def test_run_all_ok(self):
        m = parse_manifest("a:\nb: a\n")
        report = Executor().run(m)
        self.assertEqual(report.counts, {"ok": 2, "skip": 0, "failed": 0})
        self.assertEqual([r.name for r in report.records], ["a", "b"])
        self.assertEqual([r.layer for r in report.records], [1, 2])

    def test_fail_cascades_to_skip(self):
        m = parse_manifest(MANIFEST)
        report = Executor(fail_targets={"tools"}).run(m)
        self.assertEqual(report.counts, {"ok": 4, "skip": 2, "failed": 1})
        status = {r.name: r.status for r in report.records}
        self.assertEqual(status["tools"], "failed")
        self.assertEqual(status["tests"], "skip")
        self.assertEqual(status["docs"], "skip")
        self.assertEqual(status["server"], "ok")

    def test_failed_keeps_cost_skip_is_zero(self):
        m = parse_manifest("a:\nb: a\n")
        report = Executor(fail_targets={"a"}).run(m)
        by_name = {r.name: r for r in report.records}
        self.assertEqual(by_name["a"].cost_ms, target_cost_ms("a"))
        self.assertEqual(by_name["b"].cost_ms, 0)

    def test_report_text_golden(self):
        m = parse_manifest(MANIFEST)
        report = Executor(fail_targets={"tools"}).run(m)
        self.assertEqual(
            report.text,
            "report: 7 target(s) in 5 layer(s)"
            " | ok=4 skip=2 failed=1 | total 31ms\n"
            "[1/5] base\n"
            "  ok     base   4ms\n"
            "[2/5] core net\n"
            "  ok     core   9ms\n"
            "  ok     net   1ms\n"
            "[3/5] server tools\n"
            "  ok     server   8ms\n"
            "  failed tools   9ms\n"
            "[4/5] tests\n"
            "  skip   tests   0ms\n"
            "[5/5] docs\n"
            "  skip   docs   0ms\n",
        )

    def test_report_layers_match_layer_targets(self):
        m = parse_manifest(MANIFEST)
        report = Executor().run(m)
        self.assertEqual(report.layers, layer_targets(m))

    def test_total_ms_sums_costs(self):
        m = parse_manifest(MANIFEST)
        report = Executor().run(m)
        self.assertEqual(
            report.total_ms, sum(target_cost_ms(n) for n in m.order)
        )

    def test_hooks_fire_in_order(self):
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
        Executor().run(m, visitor=rec)
        self.assertEqual(
            rec.events,
            [
                ("layer_start", 1, 2, ("a",)),
                ("target", "a", "ok", target_cost_ms("a")),
                ("layer_finish", 1),
                ("layer_start", 2, 2, ("b",)),
                ("target", "b", "ok", target_cost_ms("b")),
                ("layer_finish", 2),
                ("run_finish", {"ok": 2, "skip": 0, "failed": 0},
                 target_cost_ms("a") + target_cost_ms("b")),
            ],
        )


if __name__ == "__main__":
    unittest.main()
