"""防回归测试：每个测试类对应运维反馈的一个线上现象，根因见 README Known Issues。"""
import threading
import time
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scheduler import (DailyTrigger, FakeClock, IntervalTrigger, MonthlyTrigger,
                       Scheduler)

UTC = timezone.utc
T0 = datetime(2026, 3, 1, tzinfo=UTC)


def wait_until(cond, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


class DailyTriggerDstTest(unittest.TestCase):
    """现象 1：柏林 09:30 每日任务在夏令时切换日晚 1 小时，次日自愈。"""

    def test_spring_forward_keeps_wall_clock(self):
        trig = DailyTrigger(9, 30, tz="Europe/Berlin")
        prev = datetime(2026, 3, 28, 8, 30, tzinfo=UTC)  # 03-28 09:30 CET
        nxt = trig.next_after(prev)
        self.assertEqual(nxt, datetime(2026, 3, 29, 7, 30, tzinfo=UTC))  # 03-29 09:30 CEST
        self.assertEqual(nxt.astimezone(trig.tz).strftime("%H:%M"), "09:30")

    def test_autumn_fallback_keeps_wall_clock(self):
        trig = DailyTrigger(9, 30, tz="Europe/Berlin")
        prev = datetime(2026, 10, 24, 7, 30, tzinfo=UTC)  # 10-24 09:30 CEST
        nxt = trig.next_after(prev)
        self.assertEqual(nxt, datetime(2026, 10, 25, 8, 30, tzinfo=UTC))  # 10-25 09:30 CET
        self.assertEqual(nxt.astimezone(trig.tz).strftime("%H:%M"), "09:30")


class MonthlyTriggerTest(unittest.TestCase):
    """现象 4：每月 31 号 8 点的月报在 2 月 28 日误触发。"""

    def test_day_31_skips_february(self):
        trig = MonthlyTrigger(31, 8, 0, tz="Asia/Shanghai")
        prev = datetime(2026, 1, 31, 0, 0, tzinfo=UTC)  # 01-31 08:00 CST
        local = trig.next_after(prev).astimezone(trig.tz)
        self.assertEqual((local.year, local.month, local.day), (2026, 3, 31))
        self.assertEqual((local.hour, local.minute), (8, 0))

    def test_day_30_skips_february(self):
        trig = MonthlyTrigger(30, 8, 0, tz="Asia/Shanghai")
        prev = datetime(2026, 1, 30, 0, 0, tzinfo=UTC)
        local = trig.next_after(prev).astimezone(trig.tz)
        self.assertEqual((local.year, local.month, local.day), (2026, 3, 30))

    def test_existing_day_still_fires_in_short_month(self):
        trig = MonthlyTrigger(15, 8, 0, tz="Asia/Shanghai")
        prev = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        local = trig.next_after(prev).astimezone(trig.tz)
        self.assertEqual((local.year, local.month, local.day), (2026, 2, 15))


class MisfireTest(unittest.TestCase):
    """现象 3：时钟前跳后，早已过期的任务被疯狂补跑，轻微迟到的反而一个没跑。"""

    def test_slightly_late_task_runs_exactly_once(self):
        clock = FakeClock(T0)
        sched = Scheduler(clock, worker_count=1, tick=0.05, misfire_grace=30.0)
        ran = []
        sched.add("a", IntervalTrigger(timedelta(seconds=10)), lambda: ran.append(1))
        sched.start()
        try:
            clock.advance(12)  # 比到期时刻晚 ~2s，在宽限期内
            self.assertTrue(wait_until(lambda: ran), "宽限期内的任务没有执行")
            time.sleep(0.3)
            self.assertEqual(len(ran), 1)
        finally:
            sched.stop()

    def test_long_overdue_task_skipped_without_storm(self):
        clock = FakeClock(T0)
        sched = Scheduler(clock, worker_count=1, tick=0.05, misfire_grace=30.0)
        ran = []
        sched.add("b", IntervalTrigger(timedelta(seconds=10)), lambda: ran.append(1))
        sched.start()
        try:
            clock.advance(3600)  # NTP 前跳 1 小时，远超宽限期
            time.sleep(0.5)      # 旧逻辑会在此期间反复补跑
            self.assertEqual(ran, [])
            task = sched.get("b")
            self.assertGreater(task.next_run, clock.now())
            anchor = datetime(2026, 1, 1, tzinfo=UTC)
            self.assertEqual((task.next_run - anchor) % timedelta(seconds=10),
                             timedelta(0), "next_run 应保持在 anchor 网格上")
            clock.advance(10)    # 跳过过期部分后，后续照常触发
            self.assertTrue(wait_until(lambda: ran), "跳过后下一次到期未触发")
        finally:
            sched.stop()


class StaleQueueEntryTest(unittest.TestCase):
    """现象 2：任务被删除（或暂停）后，已入队的待执行项仍被执行了一次。"""

    def _blocked_scheduler(self):
        """worker 被 blocker 任务卡住，保证 doomed 的队列项在操作前不会被取走。"""
        clock = FakeClock(T0)
        sched = Scheduler(clock, worker_count=1, tick=0.05, misfire_grace=60.0)
        entered = threading.Event()
        release = threading.Event()
        sched.add("blocker", IntervalTrigger(timedelta(seconds=1)),
                  lambda: (entered.set(), release.wait(5)))
        sched.start()
        return sched, clock, entered, release

    def test_remove_while_queued_never_runs(self):
        sched, clock, entered, release = self._blocked_scheduler()
        ran = []
        sched.add("doomed", IntervalTrigger(timedelta(seconds=1)), lambda: ran.append(1))
        try:
            clock.advance(2)
            self.assertTrue(entered.wait(2))
            sched.remove("doomed")
            release.set()
            time.sleep(0.3)
            self.assertEqual(ran, [])
        finally:
            release.set()
            sched.stop()

    def test_pause_while_queued_never_runs(self):
        sched, clock, entered, release = self._blocked_scheduler()
        ran = []
        sched.add("doomed", IntervalTrigger(timedelta(seconds=1)), lambda: ran.append(1))
        try:
            clock.advance(2)
            self.assertTrue(entered.wait(2))
            sched.pause("doomed")
            release.set()
            time.sleep(0.3)
            self.assertEqual(ran, [])
            sched.resume("doomed")  # 恢复后下一次到期应正常触发
            clock.advance(10)
            self.assertTrue(wait_until(lambda: ran), "恢复后任务未再触发")
        finally:
            release.set()
            sched.stop()

    def test_remove_then_readd_same_id_ignores_stale_entry(self):
        sched, clock, entered, release = self._blocked_scheduler()
        sched.add("doomed", IntervalTrigger(timedelta(seconds=1)), lambda: None)
        ran = []
        try:
            clock.advance(2)
            self.assertTrue(entered.wait(2))
            sched.remove("doomed")
            sched.add("doomed", IntervalTrigger(timedelta(seconds=1)),
                      lambda: ran.append(1))
            release.set()
            time.sleep(0.3)  # 不再推进时钟：新任务未到期，任何执行都来自过期队列项
            self.assertEqual(ran, [])
        finally:
            release.set()
            sched.stop()


class StoreRoundTripTest(unittest.TestCase):
    """现象 5：重启后被暂停的任务自己跑起来；有的任务 next_run 整体偏 8 小时。"""

    def test_paused_and_next_run_survive_restart(self):
        sched = Scheduler(FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC)))
        sched.add("a", IntervalTrigger(timedelta(hours=1)), lambda: None, paused=True)
        sched.add("b", DailyTrigger(9, 30, tz="Europe/Berlin"), lambda: None)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "tasks.json")
            sched.save(path)
            sched2 = Scheduler(FakeClock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC)))
            sched2.load(path)
        self.assertTrue(sched2.get("a").paused, "paused 状态未持久化")
        self.assertFalse(sched2.get("b").paused)
        self.assertEqual(sched2.get("a").next_run, sched.get("a").next_run,
                         "next_run 在保存/加载后发生偏移")
        self.assertEqual(sched2.get("a").next_run.utcoffset(), timedelta(0))
        self.assertEqual(sched2.get("b").next_run, sched.get("b").next_run)


if __name__ == "__main__":
    unittest.main()
