"""retrykit 行为清单——重构期间一个字都不改，必须原样全绿。

时序用假时钟锁死：sleep 只推表不真睡，monotonic/time 由同一张表驱动。
"""

import unittest
from unittest import mock

from retrykit import RetryError, retry


class FakeClock(object):
    def __init__(self):
        self.mono = 1000.0
        self.wall = 1700000000.0
        self.sleeps = []

    def sleep(self, d):
        self.sleeps.append(d)
        self.mono += d
        self.wall += d

    def monotonic(self):
        return self.mono

    def time(self):
        return self.wall


def raiser(err):
    """一直抛 err，calls 记录调用次数。"""
    calls = []

    def fn():
        calls.append(1)
        raise err
    fn.calls = calls
    return fn


def flaky(errors, result=None):
    """依次抛 errors 里的异常，抛完后返回 result，calls 记录调用次数。"""
    pending = list(errors)
    calls = []

    def fn():
        calls.append(1)
        if pending:
            raise pending.pop(0)
        return result
    fn.calls = calls
    return fn


class LockedTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        for target, fake in (("time.sleep", self.clock.sleep),
                             ("time.monotonic", self.clock.monotonic),
                             ("time.time", self.clock.time)):
            p = mock.patch(target, fake)
            p.start()
            self.addCleanup(p.stop)


class TestFixed(LockedTestCase):
    def test_success_first_try_no_sleep(self):
        f = flaky([], result="ok")
        self.assertEqual(retry(f, attempts=4, strategy="fixed", delay=0.3), "ok")
        self.assertEqual(f.calls, [1])
        self.assertEqual(self.clock.sleeps, [])

    def test_fixed_constant_waits(self):
        f = raiser(ValueError("x"))
        with self.assertRaises(RetryError):
            retry(f, attempts=4, strategy="fixed", delay=0.5)
        self.assertEqual(self.clock.sleeps, [0.5, 0.5, 0.5])
        self.assertEqual(len(f.calls), 4)

    def test_giveup_message(self):
        with self.assertRaises(RetryError) as ctx:
            retry(raiser(ValueError("nope")), attempts=3, strategy="fixed", delay=0.1)
        self.assertEqual(
            str(ctx.exception),
            "gave up after 3 attempts, last error: ValueError('nope')")

    def test_single_attempt_no_sleep_no_callback(self):
        seen = []
        with self.assertRaises(RetryError):
            retry(raiser(ValueError("x")), attempts=1, strategy="fixed",
                  delay=0.5, on_retry=lambda *a: seen.append(a))
        self.assertEqual(self.clock.sleeps, [])
        self.assertEqual(seen, [])

    def test_falsy_return_counts_as_success(self):
        f = flaky([])
        self.assertEqual(retry(f, attempts=3, strategy="fixed", delay=0.1), None)
        self.assertEqual(len(f.calls), 1)


class TestExpo(LockedTestCase):
    def test_expo_doubling(self):
        f = raiser(ValueError("x"))
        with self.assertRaises(RetryError):
            retry(f, attempts=4, strategy="expo", delay=0.5)
        self.assertEqual(self.clock.sleeps, [0.5, 1.0, 2.0])

    def test_expo_capped(self):
        f = raiser(ValueError("x"))
        with self.assertRaises(RetryError):
            retry(f, attempts=5, strategy="expo", delay=0.5, max_delay=1.2)
        self.assertEqual(self.clock.sleeps, [0.5, 1.0, 1.2, 1.2])

    def test_expo_uncapped_when_max_delay_none(self):
        f = raiser(ValueError("x"))
        with self.assertRaises(RetryError):
            retry(f, attempts=5, strategy="expo", delay=0.5)
        self.assertEqual(self.clock.sleeps, [0.5, 1.0, 2.0, 4.0])

    def test_expo_giveup_message(self):
        with self.assertRaises(RetryError) as ctx:
            retry(raiser(ValueError("x")), attempts=2, strategy="expo", delay=0.5)
        self.assertEqual(
            str(ctx.exception),
            "gave up after 2 attempts, last error: ValueError('x')")

    def test_expo_success_after_retries(self):
        f = flaky([ValueError("a"), ValueError("b")], result="done")
        self.assertEqual(retry(f, attempts=5, strategy="expo", delay=0.5), "done")
        self.assertEqual(self.clock.sleeps, [0.5, 1.0])
        self.assertEqual(len(f.calls), 3)


class TestJitter(LockedTestCase):
    def test_jitter_uniform_args_and_sleeps(self):
        calls = []

        def fake_uniform(lo, hi):
            calls.append((lo, hi))
            return hi / 2

        p = mock.patch("random.uniform", fake_uniform)
        p.start()
        self.addCleanup(p.stop)
        f = raiser(ValueError("x"))
        with self.assertRaises(RetryError):
            retry(f, attempts=4, strategy="jitter", delay=0.5, max_delay=1.2)
        self.assertEqual(calls, [(0, 0.5), (0, 1.0), (0, 1.2)])
        self.assertEqual(self.clock.sleeps, [0.25, 0.5, 0.6])

    def test_jitter_giveup_message(self):
        with self.assertRaises(RetryError) as ctx:
            retry(raiser(ValueError("x")), attempts=3, strategy="jitter", delay=0.5)
        self.assertEqual(
            str(ctx.exception),
            "gave up after 3 attempts, last error: ValueError('x')")


class TestRetryOn(LockedTestCase):
    def test_non_retryable_propagates_original(self):
        err = KeyError("k")
        f = raiser(err)
        with self.assertRaises(KeyError) as ctx:
            retry(f, attempts=3, strategy="fixed", delay=0.1, retry_on=(ValueError,))
        self.assertIs(ctx.exception, err)
        self.assertEqual(self.clock.sleeps, [])

    def test_retry_on_multiple_classes(self):
        f = flaky([TimeoutError("slow")], result="ok")
        self.assertEqual(
            retry(f, attempts=3, strategy="fixed", delay=0.1,
                  retry_on=(ValueError, TimeoutError)), "ok")

    def test_keyboard_interrupt_not_caught_by_default(self):
        f = raiser(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):
            retry(f, attempts=3, strategy="fixed", delay=0.1)
        self.assertEqual(self.clock.sleeps, [])

    def test_default_catches_runtime_error(self):
        with self.assertRaises(RetryError):
            retry(raiser(RuntimeError("r")), attempts=2, strategy="fixed", delay=0.1)


class TestOnRetry(LockedTestCase):
    def test_on_retry_args_and_order(self):
        err_a = ValueError("a")
        err_b = ValueError("b")
        seen = []
        f = flaky([err_a, err_b], result="ok")
        self.assertEqual(
            retry(f, attempts=3, strategy="fixed", delay=0.2,
                  on_retry=lambda n, e, w: seen.append((n, e, w))), "ok")
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][0], 1)
        self.assertIs(seen[0][1], err_a)
        self.assertEqual(seen[0][2], 0.2)
        self.assertEqual(seen[1][0], 2)
        self.assertIs(seen[1][1], err_b)

    def test_on_retry_skipped_on_final_failure(self):
        seen = []
        with self.assertRaises(RetryError):
            retry(raiser(ValueError("x")), attempts=2, strategy="fixed",
                  delay=0.3, on_retry=lambda *a: seen.append(a))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0], (1, seen[0][1], 0.3))

    def test_on_retry_skipped_on_non_retryable(self):
        seen = []
        with self.assertRaises(KeyError):
            retry(raiser(KeyError("k")), attempts=3, strategy="fixed",
                  delay=0.1, retry_on=(ValueError,),
                  on_retry=lambda *a: seen.append(a))
        self.assertEqual(seen, [])

    def test_on_retry_waits_for_expo(self):
        seen = []
        f = flaky([ValueError("x"), ValueError("x")], result=1)
        retry(f, attempts=3, strategy="expo", delay=0.5,
              on_retry=lambda n, e, w: seen.append(w))
        self.assertEqual(seen, [0.5, 1.0])


class TestBudget(LockedTestCase):
    def test_budget_message_and_calls(self):
        seen = []
        f = raiser(ValueError("x"))
        with self.assertRaises(RetryError) as ctx:
            retry(f, attempts=5, strategy="fixed", delay=0.4, timeout=0.5,
                  on_retry=lambda *a: seen.append(a))
        self.assertEqual(
            str(ctx.exception),
            "budget of 0.50s exceeded after 3 attempts, last error: ValueError('x')")
        self.assertEqual(self.clock.sleeps, [0.4, 0.4])
        self.assertEqual(len(seen), 2)

    def test_budget_boundary_equal_gives_up(self):
        with self.assertRaises(RetryError) as ctx:
            retry(raiser(ValueError("x")), attempts=4, strategy="fixed",
                  delay=0.5, timeout=0.5)
        self.assertEqual(
            str(ctx.exception),
            "budget of 0.50s exceeded after 2 attempts, last error: ValueError('x')")
        self.assertEqual(self.clock.sleeps, [0.5])

    def test_budget_none_never_trips(self):
        with self.assertRaises(RetryError) as ctx:
            retry(raiser(ValueError("x")), attempts=3, strategy="fixed", delay=10.0)
        self.assertEqual(
            str(ctx.exception),
            "gave up after 3 attempts, last error: ValueError('x')")

    def test_budget_expo_path(self):
        seen = []
        with self.assertRaises(RetryError) as ctx:
            retry(raiser(ValueError("x")), attempts=6, strategy="expo",
                  delay=1.0, timeout=1.5, on_retry=lambda *a: seen.append(a))
        self.assertEqual(
            str(ctx.exception),
            "budget of 1.50s exceeded after 3 attempts, last error: ValueError('x')")
        self.assertEqual(self.clock.sleeps, [1.0, 2.0])
        self.assertEqual(len(seen), 2)


class TestValidation(LockedTestCase):
    def test_attempts_zero_raises(self):
        f = flaky([])
        with self.assertRaises(ValueError) as ctx:
            retry(f, attempts=0, strategy="fixed", delay=0.1)
        self.assertEqual(str(ctx.exception), "attempts must be >= 1")
        self.assertEqual(f.calls, [])

    def test_negative_delay_raises(self):
        with self.assertRaises(ValueError) as ctx:
            retry(flaky([]), attempts=2, strategy="fixed", delay=-0.1)
        self.assertEqual(str(ctx.exception), "delay must be >= 0")

    def test_unknown_strategy(self):
        f = flaky([])
        with self.assertRaises(ValueError) as ctx:
            retry(f, strategy="linear")
        self.assertEqual(str(ctx.exception), "unknown strategy: linear")
        self.assertEqual(f.calls, [])


class TestPassthrough(LockedTestCase):
    def test_return_value_identity(self):
        sentinel = object()
        self.assertIs(retry(flaky([], result=sentinel)), sentinel)

    def test_attempts_counts_first_call(self):
        f = flaky([ValueError("x")], result="ok")
        self.assertEqual(retry(f, attempts=2, strategy="fixed", delay=0.1), "ok")
        self.assertEqual(len(f.calls), 2)
        self.assertEqual(self.clock.sleeps, [0.1])


if __name__ == "__main__":
    unittest.main()
