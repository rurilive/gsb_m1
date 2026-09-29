"""Runner 现有行为的锁定测试：登记、顺序执行、失败传播。

只覆盖当前已支持的顺序执行能力。分支、并行、补偿、状态机与检查点重试
等新行为另开 tests/test_orchestra.py，本文件一字不改。
"""

import unittest

from orchestra import (
    DuplicateStep,
    InvalidStepName,
    OrchestraError,
    Runner,
    StepNotFound,
)
from orchestra.runner import Runner as RunnerFromModule, require_step


def build():
    """三个步骤的直线流程：a 产出 x，b 读 x 产出 y，c 读 y 产出 z。"""
    r = Runner()
    r.add_step("a", lambda ctx: {"x": 1})
    r.add_step("b", lambda ctx: {"y": ctx["x"] + 1})
    r.add_step("c", lambda ctx: {"z": ctx["y"] + 1})
    return r


class TestRegistration(unittest.TestCase):
    def test_steps_preserve_order(self):
        self.assertEqual(build().steps(), ["a", "b", "c"])

    def test_has_step(self):
        r = build()
        self.assertTrue(r.has_step("a"))
        self.assertFalse(r.has_step("zzz"))

    def test_add_step_returns_self(self):
        r = Runner()
        self.assertIs(r.add_step("a", lambda ctx: None), r)

    def test_empty_name_is_rejected(self):
        with self.assertRaises(InvalidStepName):
            Runner().add_step("", lambda ctx: None)

    def test_non_string_name_is_rejected(self):
        with self.assertRaises(InvalidStepName):
            Runner().add_step(7, lambda ctx: None)

    def test_duplicate_step_is_rejected(self):
        r = Runner()
        r.add_step("a", lambda ctx: None)
        with self.assertRaises(DuplicateStep):
            r.add_step("a", lambda ctx: None)

    def test_non_callable_is_rejected(self):
        with self.assertRaises(OrchestraError):
            Runner().add_step("a", 42)

    def test_rejected_step_is_not_registered(self):
        r = Runner()
        r.add_step("a", lambda ctx: None)
        try:
            r.add_step("a", lambda ctx: None)
        except DuplicateStep:
            pass
        self.assertEqual(r.steps(), ["a"])


class TestExecution(unittest.TestCase):
    def test_runs_in_registration_order(self):
        r = Runner()
        seen = []
        r.add_step("a", lambda ctx: seen.append("a"))
        r.add_step("b", lambda ctx: seen.append("b"))
        r.add_step("c", lambda ctx: seen.append("c"))
        r.execute()
        self.assertEqual(seen, ["a", "b", "c"])

    def test_dict_results_are_merged_into_context(self):
        ctx = build().execute()
        self.assertEqual(ctx, {"x": 1, "y": 2, "z": 3})

    def test_passed_context_is_reused(self):
        r = Runner()
        r.add_step("a", lambda ctx: {"seen": ctx.get("seed")})
        ctx = r.execute({"seed": 5})
        self.assertEqual(ctx["seen"], 5)
        self.assertEqual(ctx["seed"], 5)

    def test_none_result_is_ignored(self):
        r = Runner()
        r.add_step("a", lambda ctx: None)
        self.assertEqual(r.execute(), {})

    def test_executed_records_successful_steps(self):
        r = build()
        r.execute()
        self.assertEqual(r.executed, ["a", "b", "c"])

    def test_executed_is_a_copy(self):
        r = build()
        r.execute()
        r.executed.append("hacked")
        self.assertEqual(r.executed, ["a", "b", "c"])

    def test_rerun_resets_executed(self):
        r = build()
        r.execute()
        r.execute()
        self.assertEqual(r.executed, ["a", "b", "c"])

    def test_empty_runner_executes_to_empty_context(self):
        self.assertEqual(Runner().execute(), {})


class TestFailurePropagation(unittest.TestCase):
    def test_exception_is_not_swallowed(self):
        r = Runner()
        r.add_step("a", lambda ctx: {"x": 1})
        r.add_step("b", lambda ctx: (_ for _ in ()).throw(ValueError("boom")))
        with self.assertRaises(ValueError):
            r.execute()

    def test_executed_stops_at_failure(self):
        r = Runner()
        r.add_step("a", lambda ctx: None)
        r.add_step("b", lambda ctx: (_ for _ in ()).throw(ValueError("boom")))
        r.add_step("c", lambda ctx: None)
        with self.assertRaises(ValueError):
            r.execute()
        self.assertEqual(r.executed, ["a"])

    def test_later_steps_do_not_run_after_failure(self):
        r = Runner()
        seen = []
        r.add_step("a", lambda ctx: seen.append("a"))
        r.add_step("b", lambda ctx: (_ for _ in ()).throw(ValueError("boom")))
        r.add_step("c", lambda ctx: seen.append("c"))
        with self.assertRaises(ValueError):
            r.execute()
        self.assertEqual(seen, ["a"])


class TestHelpers(unittest.TestCase):
    def test_require_step_returns_callable(self):
        r = build()
        self.assertTrue(callable(require_step({"a": r._steps["a"]}, "a")))

    def test_require_step_missing_raises(self):
        with self.assertRaises(StepNotFound):
            require_step({}, "ghost")

    def test_repr(self):
        self.assertIn("Runner", repr(build()))

    def test_exported_from_package_and_module(self):
        self.assertIs(Runner, RunnerFromModule)


if __name__ == "__main__":
    unittest.main()