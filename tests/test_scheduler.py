"""nestrun 现有行为的锁定测试。"""

import unittest

from nestrun import (
    CANCELLED,
    FAILED,
    LEGAL_TRANSITIONS,
    PENDING,
    RUNNING,
    STATES,
    SUCCEEDED,
    Cancelled,
    InvalidTransition,
    ManualClock,
    Scheduler,
    SchedulerError,
    check_transition,
)


def make_scheduler(start=0.0):
    """手动时钟的调度器，连同它的时钟一起返回。"""
    clock = ManualClock(start)
    return Scheduler(clock=clock), clock


def advance(scheduler, clock, seconds):
    clock.advance(seconds)
    return scheduler.run()


class Recorder:
    """把每个任务的落定回调次数记下来。"""

    def __init__(self):
        self.calls = []

    def __call__(self, task):
        self.calls.append(task)

    def count(self, task):
        return sum(1 for item in self.calls if item is task)


class TestCompletion(unittest.TestCase):
    def test_task_completes_and_fires_callback_once(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        task = sched.submit("巡检", lambda task: None, on_done=rec)
        sched.run()
        self.assertEqual(task.state, SUCCEEDED)
        self.assertEqual(task.history, [PENDING, RUNNING, SUCCEEDED])
        self.assertEqual(rec.count(task), 1)
        self.assertIsNone(task.error)
        self.assertTrue(task.done)

    def test_delay_defers_start(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        task = sched.submit("夜巡", lambda task: None, delay=2.0, on_done=rec)
        sched.run()
        self.assertEqual(task.state, PENDING)
        self.assertEqual(rec.count(task), 0)
        advance(sched, clock, 2.0)
        self.assertEqual(task.state, SUCCEEDED)
        self.assertEqual(rec.count(task), 1)

    def test_timeout_budget_is_revoked_after_early_completion(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        task = sched.submit("值班", lambda task: None, delay=0.5, timeout=5.0,
                            on_done=rec)
        advance(sched, clock, 0.5)
        self.assertEqual(task.state, SUCCEEDED)
        advance(sched, clock, 60.0)
        advance(sched, clock, 60.0)
        self.assertEqual(task.state, SUCCEEDED)
        self.assertEqual(rec.count(task), 1)

    def test_body_error_fails_task(self):
        sched, clock = make_scheduler()
        rec = Recorder()

        def boom(task):
            raise ValueError("磁盘写满了")

        task = sched.submit("落库", boom, on_done=rec)
        sched.run()
        self.assertEqual(task.state, FAILED)
        self.assertIsInstance(task.error, ValueError)
        self.assertEqual(str(task.error), "磁盘写满了")
        self.assertEqual(task.history, [PENDING, RUNNING, FAILED])
        self.assertEqual(rec.count(task), 1)

    def test_newest_tasks_run_in_submit_order(self):
        sched, clock = make_scheduler()
        started = []

        def body(task):
            started.append(task.name)

        for name in ("甲", "乙", "丙"):
            sched.submit(name, body)
        sched.run()
        self.assertEqual(started, ["甲", "乙", "丙"])


class TestNested(unittest.TestCase):
    def test_parent_waits_for_all_children(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        seen = []

        def body(task):
            task.spawn("解析", lambda t: seen.append("解析"), delay=1.0, on_done=rec)
            task.spawn("落库", lambda t: seen.append("落库"), delay=3.0, on_done=rec)

        root = sched.submit("编排", body, on_done=rec)
        sched.run()
        self.assertEqual(root.state, RUNNING)
        self.assertEqual(len(root.children), 2)
        advance(sched, clock, 1.0)
        self.assertEqual(root.state, RUNNING)
        advance(sched, clock, 2.0)
        self.assertEqual(seen, ["解析", "落库"])
        self.assertEqual([child.state for child in root.children], [SUCCEEDED, SUCCEEDED])
        self.assertEqual(root.state, SUCCEEDED)
        self.assertEqual(rec.count(root), 1)
        for child in root.children:
            self.assertEqual(rec.count(child), 1)
        # 子任务的回调先于父任务的回调。
        self.assertEqual(rec.calls[-1], root)

    def test_spawn_from_settled_task_raises(self):
        sched, clock = make_scheduler()
        task = sched.submit("巡检", lambda task: None)
        sched.run()
        with self.assertRaises(SchedulerError):
            task.spawn("补录", lambda t: None)


class TestCancel(unittest.TestCase):
    def test_cancel_before_run_keeps_task_cancelled(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        task = sched.submit("巡检", lambda task: None, on_done=rec)
        self.assertTrue(task.cancel("运维手动取消"))
        self.assertEqual(task.state, CANCELLED)
        self.assertIsInstance(task.error, Cancelled)
        self.assertEqual(task.error.reason, "运维手动取消")
        sched.run()
        self.assertEqual(task.state, CANCELLED)
        self.assertEqual(rec.count(task), 1)
        advance(sched, clock, 30.0)
        self.assertEqual(task.state, CANCELLED)
        self.assertEqual(rec.count(task), 1)

    def test_cancelled_task_with_delay_does_not_start_later(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        task = sched.submit("巡检", lambda task: None, delay=2.0, on_done=rec)
        task.cancel("值班取消")
        advance(sched, clock, 10.0)
        self.assertEqual(task.state, CANCELLED)
        self.assertEqual(rec.count(task), 1)

    def test_timeout_cancels_a_task_that_never_started(self):
        sched, clock = make_scheduler()
        rec = Recorder()
        task = sched.submit("慢任务", lambda task: None, delay=1.0, timeout=0.5,
                            on_done=rec)
        sched.run()
        advance(sched, clock, 0.5)
        self.assertEqual(task.state, CANCELLED)
        self.assertEqual(task.error.reason, "timeout")
        self.assertEqual(rec.count(task), 1)
        advance(sched, clock, 10.0)
        self.assertEqual(task.state, CANCELLED)
        self.assertEqual(rec.count(task), 1)


class TestCallbacksAndStates(unittest.TestCase):
    def test_callback_added_after_settle_fires_immediately_once(self):
        sched, clock = make_scheduler()
        task = sched.submit("巡检", lambda task: None)
        sched.run()
        rec = Recorder()
        task.add_done_callback(rec)
        self.assertEqual(rec.count(task), 1)

    def test_state_properties(self):
        sched, clock = make_scheduler()
        task = sched.submit("巡检", lambda task: None)
        self.assertFalse(task.done)
        self.assertFalse(task.cancelled)
        sched.run()
        self.assertTrue(task.done)
        self.assertFalse(task.cancelled)

    def test_legal_transition_table(self):
        self.assertEqual(LEGAL_TRANSITIONS[PENDING], (RUNNING, CANCELLED))
        self.assertEqual(LEGAL_TRANSITIONS[RUNNING], (SUCCEEDED, FAILED, CANCELLED))

    def test_check_transition_accepts_legal_pairs(self):
        for current in STATES:
            for target in LEGAL_TRANSITIONS[current]:
                self.assertEqual(check_transition(current, target), target)

    def test_check_transition_rejects_illegal_pairs(self):
        for current in STATES:
            for target in STATES:
                if target in LEGAL_TRANSITIONS[current]:
                    continue
                with self.assertRaises(InvalidTransition):
                    check_transition(current, target)

    def test_settled_states_have_no_way_out(self):
        for state in (SUCCEEDED, FAILED, CANCELLED):
            self.assertEqual(LEGAL_TRANSITIONS[state], ())


if __name__ == "__main__":
    unittest.main()
