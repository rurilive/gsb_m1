"""调度器行为防回归测试：misfire 策略、删除/暂停语义、持久化恢复。"""
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scheduler import FakeClock, IntervalTrigger, Scheduler

T0 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)


def wait_for(cond, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


class SchedulerTestBase(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock(T0)
        self.sched = Scheduler(self.clock, worker_count=1, tick=0.05,
                               misfire_grace=30.0)

    def tearDown(self):
        self.sched.stop()
        self.clock.advance(1)


class MisfirePolicyTest(SchedulerTestBase):
    """现象 3：时钟前跳后过期任务疯狂补跑，稍晚到的任务反而不执行。"""

    def test_clock_jump_forward_no_catchup_storm(self):
        calls = []
        self.sched.add("t", IntervalTrigger(timedelta(seconds=10)),
                       lambda: calls.append(1))
        self.sched.start()
        self.clock.jump_to(T0 + timedelta(hours=1))
        self.assertTrue(wait_for(lambda: self.sched.get("t").next_run
                                 > self.clock.now()))
        self.assertEqual(calls, [])
        self.clock.advance(11)
        self.assertTrue(wait_for(lambda: len(calls) == 1))
        self.clock.advance(10)
        self.assertTrue(wait_for(lambda: len(calls) == 2))

    def test_slightly_late_task_still_runs(self):
        calls = []
        self.sched.add("t", IntervalTrigger(timedelta(seconds=10)),
                       lambda: calls.append(1))
        self.sched.start()
        self.clock.jump_to(T0 + timedelta(seconds=15))
        self.assertTrue(wait_for(lambda: len(calls) == 1))
        self.assertGreater(self.sched.get("t").next_run, self.clock.now())


class RemovePauseSemanticsTest(SchedulerTestBase):
    """现象 2：任务被删除（或暂停）后，已入队的一次触发仍被执行。"""

    def _setup_blocked_worker(self):
        entered = threading.Event()
        release = threading.Event()

        def blocker():
            entered.set()
            release.wait(2)

        victim_calls = []
        self.sched.add("blocker", IntervalTrigger(timedelta(seconds=10)), blocker)
        self.sched.add("victim", IntervalTrigger(timedelta(seconds=10)),
                       lambda: victim_calls.append(1))
        self.sched.start()
        self.clock.advance(11)
        self.assertTrue(entered.wait(2))
        self.assertTrue(self.sched.wait_queue_len(1, timeout=2))
        return release, victim_calls

    def test_removed_task_not_executed(self):
        release, victim_calls = self._setup_blocked_worker()
        self.sched.remove("victim")
        release.set()
        self.assertTrue(self.sched.wait_idle(2))
        self.assertEqual(victim_calls, [])

    def test_paused_task_not_executed_then_resume_works(self):
        release, victim_calls = self._setup_blocked_worker()
        self.sched.pause("victim")
        release.set()
        self.assertTrue(self.sched.wait_idle(2))
        self.assertEqual(victim_calls, [])
        self.sched.resume("victim")
        self.clock.advance(20)
        self.assertTrue(wait_for(lambda: len(victim_calls) == 1))

    def test_paused_task_never_fires(self):
        calls = []
        self.sched.add("t", IntervalTrigger(timedelta(seconds=10)),
                       lambda: calls.append(1), paused=True)
        self.sched.start()
        self.clock.advance(55)
        time.sleep(0.2)
        self.assertEqual(calls, [])
        self.sched.resume("t")
        for _ in range(3):
            self.clock.advance(10)
            time.sleep(0.1)
        self.assertTrue(wait_for(lambda: len(calls) >= 1))


class PersistenceTest(SchedulerTestBase):
    """现象 5：重启后 paused 丢失、next_run 偏移 8 小时。"""

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "tasks.json")
            self.sched.add("paused-job", IntervalTrigger(timedelta(seconds=60)),
                           lambda: None, paused=True)
            self.sched.add("active-job", IntervalTrigger(timedelta(seconds=60)),
                           lambda: None)
            expected_next = self.sched.get("active-job").next_run
            self.sched.save(path)

            restored = Scheduler(self.clock)
            restored.load(path)
            self.assertTrue(restored.get("paused-job").paused)
            self.assertFalse(restored.get("active-job").paused)
            self.assertEqual(restored.get("active-job").next_run, expected_next)


if __name__ == "__main__":
    unittest.main()
