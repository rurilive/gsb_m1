"""Executor 现有行为的锁定测试。

只覆盖当前实现已具备的能力：固定次数重试、返回最后一次结果、
失败向上抛出、时钟与等待函数可注入、计数与参数校验。
"""

import unittest

from resilkit.executor import Executor, RetryExhausted


class FakeClock:
    """可手动推进的假时钟，记录被推进的时长。"""

    def __init__(self, now=0.0):
        self.now = now
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class TestExecutorBasics(unittest.TestCase):
    def test_returns_result_on_first_success(self):
        ex = Executor(retries=3)
        self.assertEqual(ex.run(lambda: 42), 42)

    def test_retries_until_success(self):
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("boom")
            return "ok"

        ex = Executor(retries=5)
        self.assertEqual(ex.run(flaky), "ok")
        self.assertEqual(len(calls), 3)

    def test_raises_retry_exhausted_with_last_error(self):
        def always():
            raise KeyError("nope")

        ex = Executor(retries=2)
        with self.assertRaises(RetryExhausted) as ctx:
            ex.run(always)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertIsInstance(ctx.exception.last, KeyError)

    def test_zero_retries_means_single_attempt(self):
        calls = []

        def once():
            calls.append(1)
            raise ValueError("x")

        ex = Executor(retries=0)
        with self.assertRaises(RetryExhausted):
            ex.run(once)
        self.assertEqual(len(calls), 1)

    def test_args_and_kwargs_are_forwarded(self):
        ex = Executor(retries=1)
        self.assertEqual(ex.run(lambda a, b, c=0: a + b + c, 1, 2, c=3), 6)

    def test_run_or_none_swallows_exhaustion(self):
        ex = Executor(retries=1)
        self.assertIsNone(ex.run_or_none(lambda: (_ for _ in ()).throw(ValueError("x"))))
        self.assertEqual(ex.run_or_none(lambda: 7), 7)


class TestExecutorConfig(unittest.TestCase):
    def test_retries_property(self):
        self.assertEqual(Executor(retries=4).retries, 4)

    def test_negative_retries_raises(self):
        with self.assertRaises(ValueError):
            Executor(retries=-1)

    def test_clock_is_injectable(self):
        clk = FakeClock(now=5.0)
        ex = Executor(retries=1, clock=clk, sleep=clk.sleep)
        self.assertIs(ex._clock, clk)

    def test_sleep_is_injectable(self):
        clk = FakeClock()
        ex = Executor(retries=3, clock=clk, sleep=clk.sleep)
        self.assertEqual(ex._sleep.__self__, clk)

    def test_no_wait_between_attempts(self):
        clk = FakeClock()
        calls = []

        def flaky():
            calls.append(1)
            raise RuntimeError("retry me")

        ex = Executor(retries=3, clock=clk, sleep=clk.sleep)
        with self.assertRaises(RetryExhausted):
            ex.run(flaky)
        self.assertEqual(len(calls), 4)   # 当前实现立即重试，不推进时钟
        self.assertEqual(clk.slept, [])


if __name__ == "__main__":
    unittest.main()