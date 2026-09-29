"""StepRunner 基线行为的锁定测试。

只覆盖当前实现已经具备的能力：顺序执行、返回值收集、
任一步失败即整体停止、后续步骤不执行。
新增的 saga 行为（补偿、重试、超时、幂等、持久化恢复）另建
tests/test_saga.py，不改动本文件。
"""

import unittest

from sagakit import StepRunner


class TestStepRunner(unittest.TestCase):
    def test_runs_steps_in_order(self):
        calls = []

        def make(name):
            def step():
                calls.append(name)
                return name.upper()

            return step

        runner = StepRunner([make("a"), make("b"), make("c")])
        self.assertEqual(runner.run(), ["A", "B", "C"])
        self.assertEqual(calls, ["a", "b", "c"])

    def test_empty_steps_returns_empty_list(self):
        self.assertEqual(StepRunner([]).run(), [])

    def test_stops_on_first_failure(self):
        calls = []

        def ok():
            calls.append("ok")
            return 1

        def boom():
            calls.append("boom")
            raise RuntimeError("step failed")

        def never():
            calls.append("never")
            return 3

        runner = StepRunner([ok, boom, never])
        with self.assertRaises(RuntimeError):
            runner.run()
        self.assertEqual(calls, ["ok", "boom"])

    def test_len_reflects_step_count(self):
        self.assertEqual(len(StepRunner([lambda: 1, lambda: 2])), 2)

    def test_steps_snapshot_is_independent(self):
        source = [lambda: 1]
        runner = StepRunner(source)
        source.append(lambda: 2)
        self.assertEqual(len(runner), 1)


if __name__ == "__main__":
    unittest.main()
