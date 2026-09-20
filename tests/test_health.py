"""常驻自检：探针超时、状态翻转与 k/n 就绪门限的测试。

检查循环的节奏由注入的 FakeClock 控制：循环每轮结束后卡在
clock.sleep 里的 Event 上，测试 tick() 一次才放行下一轮，
因此状态翻转序列完全确定，不靠真实时间碰运气。
"""

import threading
import time
import unittest

from healthd import CheckRunner


class FakeClock:
    """注入时钟：sleep 记录在案并阻塞在 gate 上，由测试逐拍放行。"""

    def __init__(self):
        self.gate = threading.Event()
        self.slept = []
        self._lock = threading.Lock()

    def now(self):
        return 0.0

    def sleep(self, seconds):
        with self._lock:
            self.slept.append(seconds)
        self.gate.wait(5.0)
        self.gate.clear()

    def tick(self):
        """放行一轮。"""
        self.gate.set()

    def wake(self):
        """stop() 时唤醒，让循环看到停止标记退出。"""
        self.gate.set()


def wait_for(cond, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.005)
    return False


def flaky_probe(flags, key):
    def check():
        if not flags[key]:
            raise RuntimeError(f"{key} down")
        return f"{key} up"
    return check


class TestProbeTimeout(unittest.TestCase):
    def test_run_once_applies_probe_timeout(self):
        runner = CheckRunner()
        runner.register("slow", lambda: time.sleep(5), timeout=0.05)
        runner.register("fast", lambda: "ok")
        start = time.monotonic()
        snap = runner.run_once()
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertFalse(snap["slow"].ok)
        self.assertIn("timeout", snap["slow"].detail)
        self.assertTrue(snap["fast"].ok)

    def test_register_rejects_bad_timeout(self):
        runner = CheckRunner()
        with self.assertRaises(ValueError):
            runner.register("x", lambda: "", timeout=0)


class TestResidentChecks(unittest.TestCase):
    def test_timeout_degrades_but_stays_ready(self):
        runner = CheckRunner(k=2)
        runner.register("a", lambda: "ok")
        runner.register("b", lambda: "ok")
        runner.register("slow", lambda: time.sleep(5), timeout=0.05)
        clock = FakeClock()
        changes = []
        runner.on_change(lambda old, new: changes.append((old, new)))
        runner.start(period=1.0, jitter=0.0, clock=clock)
        try:
            self.assertTrue(wait_for(
                lambda: runner.status() == "degraded"
                and "slow" in runner.board.snapshot()
            ))
            self.assertTrue(runner.ready())  # 2/3 通过，达到 k=2
            snap = runner.board.snapshot()
            self.assertFalse(snap["slow"].ok)
            self.assertIn("timeout", snap["slow"].detail)
            self.assertTrue(wait_for(lambda: changes == [("down", "degraded")]))
            self.assertTrue(wait_for(lambda: len(clock.slept) >= 1))
            self.assertTrue(all(s == 1.0 for s in clock.slept))  # jitter=0 不抖动
        finally:
            runner.stop()

    def test_recovery_flips_back_to_ok(self):
        flags = {"flaky": False}
        runner = CheckRunner(k=1)
        runner.register("a", lambda: "ok")
        runner.register("flaky", flaky_probe(flags, "flaky"))
        clock = FakeClock()
        changes = []
        runner.on_change(lambda old, new: changes.append((old, new)))
        runner.start(period=1.0, jitter=0.0, clock=clock)
        try:
            self.assertTrue(wait_for(lambda: runner.status() == "degraded"))
            flags["flaky"] = True
            clock.tick()
            self.assertTrue(wait_for(lambda: runner.status() == "ok"))
            self.assertTrue(runner.ready())
            self.assertTrue(wait_for(lambda: len(changes) >= 2))
            self.assertEqual(changes, [("down", "degraded"), ("degraded", "ok")])
        finally:
            runner.stop()

    def test_kn_threshold_flips_ready(self):
        flags = {"b": True, "c": True}
        runner = CheckRunner(k=2)
        runner.register("a", lambda: "ok")
        runner.register("b", flaky_probe(flags, "b"))
        runner.register("c", flaky_probe(flags, "c"))
        clock = FakeClock()
        changes = []
        runner.on_change(lambda old, new: changes.append((old, new)))
        runner.start(period=1.0, jitter=0.0, clock=clock)
        try:
            self.assertTrue(wait_for(lambda: runner.status() == "ok"))
            self.assertTrue(runner.ready())

            flags["b"] = False
            clock.tick()
            self.assertTrue(wait_for(lambda: runner.status() == "degraded"))
            self.assertTrue(runner.ready())  # 2/3 >= k=2，仍可接流量

            flags["c"] = False
            clock.tick()
            self.assertTrue(wait_for(lambda: runner.status() == "down"))
            self.assertFalse(runner.ready())  # 1/3 < k=2，摘流量

            self.assertTrue(wait_for(lambda: len(changes) >= 3))
            self.assertEqual(
                changes,
                [("down", "ok"), ("ok", "degraded"), ("degraded", "down")],
            )
        finally:
            runner.stop()

    def test_on_change_error_does_not_break_loop(self):
        flags = {"flaky": True}
        runner = CheckRunner(k=1)
        runner.register("flaky", flaky_probe(flags, "flaky"))
        calls = []

        def bad(old, new):
            raise RuntimeError("callback boom")

        runner.on_change(bad)
        runner.on_change(lambda old, new: calls.append((old, new)))
        clock = FakeClock()
        runner.start(period=1.0, jitter=0.0, clock=clock)
        try:
            self.assertTrue(wait_for(lambda: runner.status() == "ok"))
            flags["flaky"] = False
            clock.tick()
            self.assertTrue(wait_for(lambda: runner.status() == "down"))
            flags["flaky"] = True
            clock.tick()
            self.assertTrue(wait_for(lambda: runner.status() == "ok"))
            self.assertTrue(wait_for(lambda: len(calls) >= 3))
            self.assertEqual(
                calls,
                [("down", "ok"), ("ok", "down"), ("down", "ok")],
            )
        finally:
            runner.stop()

    def test_period_jitter_bounds(self):
        runner = CheckRunner(k=1)
        runner.register("a", lambda: "ok")
        clock = FakeClock()
        runner.start(period=1.0, jitter=0.2, clock=clock)
        try:
            self.assertTrue(wait_for(lambda: len(clock.slept) >= 1))
            clock.tick()
            self.assertTrue(wait_for(lambda: len(clock.slept) >= 2))
            clock.tick()
            self.assertTrue(wait_for(lambda: len(clock.slept) >= 3))
        finally:
            runner.stop()
        for s in clock.slept:
            self.assertTrue(0.8 <= s <= 1.2, f"sleep {s} out of jitter bounds")

    def test_start_twice_raises_and_stop_idempotent(self):
        runner = CheckRunner(k=1)
        runner.register("a", lambda: "ok")
        clock = FakeClock()
        runner.start(period=1.0, clock=clock)
        try:
            with self.assertRaises(RuntimeError):
                runner.start(period=1.0, clock=clock)
        finally:
            runner.stop()
        runner.stop()  # 重复 stop 无害


if __name__ == "__main__":
    unittest.main()
