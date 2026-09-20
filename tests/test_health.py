"""常驻自检的行为测试：注入时钟 + Event 定节奏，不依赖墙钟等待。"""

import random
import threading
import time
import unittest

from healthd import CheckRunner
from healthd.checker import DEGRADED, DOWN, OK


class EventClock:
    """注入时钟：sleep 阻塞在 tick 上，由测试手动放行一轮；
    stop_event 置位时立即返回，保证 stop() 能干净退出。
    """

    def __init__(self):
        self.tick = threading.Event()
        self.now = 0.0
        self.delays = []

    def time(self):
        return self.now

    def sleep(self, seconds, stop_event=None):
        self.delays.append(seconds)
        while True:
            if stop_event is not None and stop_event.wait(timeout=0.01):
                return
            if self.tick.wait(timeout=0.01):
                self.tick.clear()
                return


class Case:
    """一组共享的测试设施：放行一轮并等回调落定。"""

    def __init__(self, **kwargs):
        self.clock = EventClock()
        self.runner = CheckRunner(clock=self.clock, **kwargs)
        self.changes = []
        self._lock = threading.Lock()
        self.runner.on_change(self._record)

    def _record(self, old, new):
        with self._lock:
            self.changes.append((old, new))

    def start(self):
        self.runner.start()
        self.wait_round_done()

    def wait_round_done(self, timeout=3.0):
        """等首轮结果写进状态板（首轮状态不一定翻转）。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.runner.board.snapshot():
                return
            time.sleep(0.005)
        raise AssertionError("first round never recorded any result")

    def advance(self, expected=None):
        """放行下一轮，等状态板更新完，返回本轮后的状态。"""
        self.clock.tick.set()
        if expected is None:
            time.sleep(0.05)
        else:
            self.wait_status(expected)
        return self.runner.status()

    def wait_changes(self, count, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if len(self.changes) >= count:
                    return list(self.changes)
            time.sleep(0.005)
        raise AssertionError(f"expected {count} changes, got {self.changes}")

    def wait_status(self, expected, timeout=3.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.runner.status() == expected:
                return
            time.sleep(0.005)
        raise AssertionError(
            f"expected status {expected}, got {self.runner.status()}")

    def stop(self):
        self.runner.stop()


class TestTimeoutDegradeRecover(unittest.TestCase):
    def setUp(self):
        # k=1：至少 1 个通过就接流量。慢探针超时后剩 1 通过 -> degraded。
        self.case = Case(period=1.0, jitter=0.2, k=1)
        r = self.case.runner
        self.block_slow = threading.Event()
        self.slow_release = threading.Event()
        self.fail_db = threading.Event()
        self.addCleanup(self._release_slow)

        def slow():
            if not self.block_slow.is_set():
                return "slow ok"
            self.slow_release.wait(5)
            return "slow ok"

        def db():
            if self.fail_db.is_set():
                raise RuntimeError("db conn refused")
            return "db ok"

        r.register("slow", slow, timeout=0.1)  # 注册在前，超时也不拖整轮
        r.register("db", db)

    def _release_slow(self):
        self.slow_release.set()

    def test_timeout_degrades_then_recovers(self):
        case = self.case
        r = case.runner
        case.start()
        # 第一轮：慢探针还没卡住，两个都过 -> ok，接流量
        self.assertEqual(r.status(), OK)
        self.assertTrue(r.ready())

        # 第二轮：慢探针卡住超时，db 仍通过 -> degraded；没全过但达到
        # 门限 k=1，所以「不那么健康」但「还能接流量」
        self.block_slow.set()
        case.advance(DEGRADED)
        snap = r.board.snapshot()
        self.assertFalse(snap["slow"].ok)
        self.assertIn("timeout", snap["slow"].detail)
        self.assertTrue(snap["db"].ok)
        self.assertEqual(r.status(), DEGRADED)
        self.assertTrue(r.ready())
        self.assertEqual(case.changes, [(DOWN, OK), (OK, DEGRADED)])

        # 第三轮：db 也挂了，0 通过 -> down，摘流量
        self.fail_db.set()
        case.advance(DOWN)
        self.assertFalse(r.ready())
        self.assertEqual(case.changes[-1], (DEGRADED, DOWN))

        # 第四轮：放开卡住的探针（上一轮的线程才返回，不影响状态），
        # 本轮重新探：slow 通过、db 仍挂 -> degraded，恢复接流量
        self.block_slow.clear()
        self.slow_release.set()
        case.advance(DEGRADED)
        self.assertTrue(r.ready())
        self.assertEqual(case.changes[-1], (DOWN, DEGRADED))

        # 第五轮：db 也恢复 -> ok
        self.fail_db.clear()
        case.advance(OK)
        self.assertEqual(case.changes[-1], (DEGRADED, OK))

        case.stop()


class TestKNThresholdFlips(unittest.TestCase):
    def setUp(self):
        # 3 个探针，k=2：0 过 down，1 过 degraded，2 过 degraded，3 过 ok
        self.case = Case(period=1.0, jitter=0.0, k=2)
        r = self.case.runner
        self.gates = {"a": threading.Event(), "b": threading.Event()}
        self.ok_a = threading.Event()
        self.ok_b = threading.Event()

        def probe_a():
            if self.ok_a.is_set():
                return "a ok"
            self.gates["a"].set()
            raise RuntimeError("a down")

        def probe_b():
            if self.ok_b.is_set():
                return "b ok"
            self.gates["b"].set()
            raise RuntimeError("b down")

        r.register("a", probe_a)
        r.register("b", probe_b)
        r.register("c", lambda: "c ok")  # 注册在最后，一轮跑完即放行节奏

    def _failing_round(self, case, name, gate):
        case.clock.tick.set()
        gate.wait(3)
        gate.clear()

    def test_status_flips_with_pass_count(self):
        case = self.case
        r = case.runner
        case.start()
        # 第一轮：仅 c 通过，1 < k -> down，不接流量
        self.assertEqual(r.status(), DOWN)
        self.assertFalse(r.ready())
        # 首轮状态没翻转：无回调
        self.assertEqual(case.changes, [])

        # 修好 a：2/3 通过 -> degraded，但已经能接流量
        self.ok_a.set()
        case.advance(DEGRADED)
        self.assertTrue(r.ready())
        self.assertEqual(case.changes[-1], (DOWN, DEGRADED))

        # a 再坏：1/3 -> down，摘流量
        self.ok_a.clear()
        self._failing_round(case, r, self.gates["a"])
        case.wait_status(DOWN)
        self.assertFalse(r.ready())
        self.assertEqual(case.changes[-1], (DEGRADED, DOWN))

        # 同时修好 a、b：3/3 -> ok
        self.ok_a.set()
        self.ok_b.set()
        case.advance(OK)
        self.assertTrue(r.ready())
        self.assertEqual(case.changes[-1], (DOWN, OK))

        # b 再坏：2/3，仍达门限 -> degraded，ready 不翻转
        self.ok_b.clear()
        self._failing_round(case, r, self.gates["b"])
        case.wait_status(DEGRADED)
        self.assertTrue(r.ready())
        self.assertEqual(case.changes[-1], (OK, DEGRADED))

        case.stop()


class TestCallbackRobustness(unittest.TestCase):
    def test_callback_exception_does_not_kill_loop(self):
        case = Case(period=1.0, jitter=0.0, k=1)
        r = case.runner
        gate = threading.Event()
        good = threading.Event()

        def flaky():
            if good.is_set():
                return "back"
            gate.set()
            raise RuntimeError("nope")

        r.register("x", flaky)

        def boom(old, new):
            raise ValueError("callback exploded")

        r.on_change(boom)

        case.start()
        self.assertEqual(r.status(), DOWN)  # 回调 boom 已被吞掉，线程还活着

        good.set()
        case.advance(OK)
        good.clear()
        case.clock.tick.set()
        gate.wait(3)
        gate.clear()
        case.wait_status(DOWN)
        # 又翻转了一轮：检查线程确实没被回调异常打死
        self.assertEqual(case.changes[-1], (OK, DOWN))
        case.stop()


class TestJitterAndLifecycle(unittest.TestCase):
    def test_delay_within_jitter_window(self):
        clock = EventClock()
        rng = random.Random(42)
        r = CheckRunner(period=10.0, jitter=2.0, clock=clock, rng=rng)
        r.register("x", lambda: "")
        r.start()
        for _ in range(5):
            clock.tick.set()
            time.sleep(0.02)
        r.stop()
        self.assertTrue(clock.delays)
        for delay in clock.delays:
            self.assertGreaterEqual(delay, 8.0)
            self.assertLessEqual(delay, 12.0)

    def test_stop_idempotent_and_restartable(self):
        clock = EventClock()
        r = CheckRunner(period=1.0, jitter=0.0, clock=clock)
        r.register("x", lambda: "")
        r.start()
        time.sleep(0.05)
        r.stop()
        r.stop()  # 重复 stop 不报错
        r.start()  # 停后可再起，状态从 down 重新计数
        time.sleep(0.05)
        self.assertEqual(r.status(), OK)
        r.stop()

    def test_start_twice_rejected(self):
        clock = EventClock()
        r = CheckRunner(clock=clock)
        r.register("x", lambda: "")
        r.start()
        try:
            with self.assertRaises(RuntimeError):
                r.start()
        finally:
            r.stop()

    def test_before_first_round_is_down_and_not_ready(self):
        clock = EventClock()
        r = CheckRunner(period=1.0, jitter=0.0, clock=clock)
        r.register("x", lambda: "")
        self.assertEqual(r.status(), DOWN)
        self.assertFalse(r.ready())

    def test_bad_timeout_rejected(self):
        r = CheckRunner()
        with self.assertRaises(ValueError):
            r.register("x", lambda: "", timeout=0)

    def test_default_k_requires_one_pass(self):
        r = CheckRunner()
        r.register("a", lambda: "")

        def fail():
            raise RuntimeError("bad")

        r.register("b", fail)
        r.run_once()
        self.assertEqual(r.status(), DEGRADED)
        self.assertTrue(r.ready())  # 默认 k=1：有一个通过就接流量


class TestSnapshotConcurrentRead(unittest.TestCase):
    def test_snapshot_safe_while_loop_writes(self):
        r = CheckRunner(period=0.01, jitter=0.0, k=1)
        r.register("a", lambda: "ok")
        r.register("b", lambda: "ok")
        stop = threading.Event()
        errors = []

        def reader():
            while not stop.is_set():
                try:
                    snap = r.board.snapshot()
                    for name, result in snap.items():
                        self.assertIn(name, ("a", "b"))
                        self.assertIsInstance(result.ok, bool)
                    r.status()
                    r.ready()
                except Exception as exc:  # 真实并发读，任何异常都算失败
                    errors.append(exc)

        t = threading.Thread(target=reader)
        r.start()
        t.start()
        time.sleep(0.3)
        stop.set()
        r.stop()
        t.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
