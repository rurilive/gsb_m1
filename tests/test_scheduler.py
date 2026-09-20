"""调度器回归测试：misfire 语义、时钟前跳、删除/暂停的陈旧任务防护。"""
import unittest
from datetime import datetime, timedelta, timezone

from scheduler import FakeClock, IntervalTrigger, Scheduler

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class SchedulerTest(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock(START)
        self.sched = Scheduler(self.clock, worker_count=1, tick=0.05,
                               misfire_grace=2.0)
        self.ran = []
        self.sched.add("job", IntervalTrigger(timedelta(seconds=10)),
                       lambda: self.ran.append(self.clock.now()))
        self.sched.start()
        self.addCleanup(self.sched.stop)

    def advance_until_idle(self, seconds, timeout=5.0):
        # 多推一个 tick，保证 loop 从注入时钟的 wait() 醒来完成扫描。
        self.clock.wait_until_waiting()
        self.clock.advance(seconds + self.sched._tick)
        self.assertTrue(self.sched.wait_idle(timeout), "队列未在超时内清空")

    def test_normal_fire_and_reschedule(self):
        self.advance_until_idle(10)
        self.assertEqual(len(self.ran), 1)
        nxt = self.sched.get("job").next_run
        self.assertEqual(nxt, START + timedelta(seconds=20))

    def test_slightly_late_still_fires(self):
        # 只晚 1 秒（< grace 2 秒）：旧实现因条件取反会静默跳过。
        self.clock.wait_until_waiting()
        nxt = self.sched.get("job").next_run
        self.clock.jump_to(nxt + timedelta(seconds=1, milliseconds=100))
        self.assertTrue(self.sched.wait_idle(5.0))
        self.assertEqual(len(self.ran), 1)

    def test_clock_forward_jump_no_catchup_storm(self):
        # NTP 前跳 1 小时：早于 grace 的 359 个槽位必须全部丢弃，只推进 next_run。
        self.clock.wait_until_waiting()
        self.clock.advance(3600 + 1)
        self.assertTrue(self.sched.wait_idle(5.0))
        self.assertEqual(self.ran, [])
        nxt = self.sched.get("job").next_run
        self.assertGreater(nxt, self.clock.now())
        self.assertEqual(nxt, START + timedelta(seconds=3610))

    def test_backward_clock_does_not_refire(self):
        # 先正常触发一次，再把时钟拨回：同一槽位不能重复入队。
        self.advance_until_idle(10)
        self.clock.wait_until_waiting()
        self.clock.jump_to(START + timedelta(seconds=5, milliseconds=100))
        self.assertTrue(self.sched.wait_idle(3.0))
        self.assertEqual(len(self.ran), 1)

    def test_remove_before_fire_never_runs(self):
        self.sched.remove("job")
        self.clock.advance(60)
        self.assertTrue(self.sched.wait_idle(3.0))
        self.assertEqual(self.ran, [])

    def test_stale_queue_entry_ignored_after_readd(self):
        # 暂停时入队的条目携带旧 generation；恢复（generation 增长）后该陈旧
        # 条目必须被 worker 拒绝，且暂停期间错过的槽位不补跑。
        self.clock.wait_until_waiting()
        self.sched.pause("job")
        self.clock.advance(61)
        self.assertTrue(self.sched.wait_idle(3.0))
        self.sched.resume("job")
        self.sched._inflight.add("job")
        self.sched._queue.put(("job", 1))  # 永远不可能存在的旧 generation
        self.assertTrue(self.sched.wait_idle(5.0))
        self.assertEqual(self.ran, [])

    def test_pause_then_advance_does_not_fire(self):
        self.sched.pause("job")
        self.clock.wait_until_waiting()
        self.clock.advance(61)
        self.assertTrue(self.sched.wait_idle(3.0))
        self.assertEqual(self.ran, [])
        self.sched.resume("job")
        # 恢复后从当前时刻重新排程，不补跑暂停期间错过的槽位。
        nxt = self.sched.get("job").next_run
        self.assertGreater(nxt, self.clock.now())
        self.clock.wait_until_waiting()
        self.clock.jump_to(nxt + timedelta(milliseconds=100))
        self.assertTrue(self.sched.wait_idle(3.0))
        self.assertEqual(len(self.ran), 1)


class OverdueMisfireTest(unittest.TestCase):

    def test_overdue_beyond_grace_skipped_once(self):
        clock = FakeClock(START)
        sched = Scheduler(clock, worker_count=1, tick=0.05, misfire_grace=60.0)
        fired = []
        # 每小时触发的任务：晚 30 秒补跑，晚 1 小时以上丢弃。
        sched.add("job", IntervalTrigger(timedelta(hours=1)), lambda: fired.append(1))
        sched.start()
        try:
            clock.wait_until_waiting()
            clock.advance(3600 + 31)  # 槽位 01:00 晚 31s <= grace=60s：补跑一次
            self.assertTrue(sched.wait_idle(5.0))
            self.assertEqual(len(fired), 1)
            clock.wait_until_waiting()
            clock.advance(3600 + 61)  # 槽位 02:00 晚 61s > grace=60s：丢弃
            self.assertTrue(sched.wait_idle(5.0))
            self.assertEqual(len(fired), 1)
        finally:
            sched.stop()


if __name__ == "__main__":
    unittest.main()
