"""触发器防回归测试：夏令时墙钟、短月跳过、间隔网格。"""
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scheduler import DailyTrigger, IntervalTrigger, MonthlyTrigger

BERLIN = ZoneInfo("Europe/Berlin")
SHANGHAI = ZoneInfo("Asia/Shanghai")


class DailyTriggerDstTest(unittest.TestCase):
    """现象 1：柏林 09:30 任务在夏令时切换日偏移 1 小时。"""

    def test_spring_forward_keeps_wall_clock(self):
        # 2026-03-29 柏林 02:00 CET -> 03:00 CEST，进入夏令时
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        t = datetime(2026, 3, 28, 9, 30, tzinfo=BERLIN)
        nxt = trigger.next_after(t)
        expected = datetime(2026, 3, 29, 9, 30, tzinfo=BERLIN)
        self.assertEqual(nxt, expected.astimezone(timezone.utc))
        self.assertEqual(nxt, datetime(2026, 3, 29, 7, 30, tzinfo=timezone.utc))

    def test_fall_back_keeps_wall_clock(self):
        # 2026-10-25 柏林 03:00 CEST -> 02:00 CET，退出夏令时
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        t = datetime(2026, 10, 24, 9, 30, tzinfo=BERLIN)
        nxt = trigger.next_after(t)
        expected = datetime(2026, 10, 25, 9, 30, tzinfo=BERLIN)
        self.assertEqual(nxt, expected.astimezone(timezone.utc))
        self.assertEqual(nxt, datetime(2026, 10, 25, 8, 30, tzinfo=timezone.utc))

    def test_normal_day_unchanged(self):
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        t = datetime(2026, 3, 10, 9, 30, tzinfo=BERLIN)
        nxt = trigger.next_after(t)
        self.assertEqual(nxt, datetime(2026, 3, 11, 8, 30, tzinfo=timezone.utc))

    def test_same_day_future_time(self):
        trigger = DailyTrigger(9, 30, tz="Asia/Shanghai")
        t = datetime(2026, 3, 10, 8, 0, tzinfo=SHANGHAI)
        nxt = trigger.next_after(t)
        self.assertEqual(nxt, datetime(2026, 3, 10, 1, 30, tzinfo=timezone.utc))


class MonthlyTriggerShortMonthTest(unittest.TestCase):
    """现象 4：31 号的月报任务在 2 月 28 日误跑。"""

    def test_day_31_skips_february(self):
        trigger = MonthlyTrigger(31, 8, 0, tz="Asia/Shanghai")
        t = datetime(2026, 2, 1, 0, 0, tzinfo=SHANGHAI)
        nxt = trigger.next_after(t)
        local = nxt.astimezone(SHANGHAI)
        self.assertEqual((local.year, local.month, local.day), (2026, 3, 31))
        self.assertEqual((local.hour, local.minute), (8, 0))

    def test_day_31_after_january_skips_february(self):
        trigger = MonthlyTrigger(31, 8, 0, tz="Asia/Shanghai")
        t = datetime(2026, 1, 31, 9, 0, tzinfo=SHANGHAI)
        nxt = trigger.next_after(t)
        local = nxt.astimezone(SHANGHAI)
        self.assertEqual((local.year, local.month, local.day), (2026, 3, 31))

    def test_day_28_fires_in_february(self):
        trigger = MonthlyTrigger(28, 8, 0, tz="Asia/Shanghai")
        t = datetime(2026, 2, 1, 0, 0, tzinfo=SHANGHAI)
        nxt = trigger.next_after(t)
        local = nxt.astimezone(SHANGHAI)
        self.assertEqual((local.year, local.month, local.day), (2026, 2, 28))

    def test_day_31_fires_on_31st_same_month(self):
        trigger = MonthlyTrigger(31, 8, 0, tz="Asia/Shanghai")
        t = datetime(2026, 3, 31, 7, 0, tzinfo=SHANGHAI)
        nxt = trigger.next_after(t)
        local = nxt.astimezone(SHANGHAI)
        self.assertEqual((local.year, local.month, local.day), (2026, 3, 31))


class IntervalTriggerGridTest(unittest.TestCase):

    def test_strictly_after_and_on_grid(self):
        anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)
        trigger = IntervalTrigger(timedelta(seconds=10), anchor=anchor)
        self.assertEqual(trigger.next_after(anchor), anchor + timedelta(seconds=10))
        self.assertEqual(trigger.next_after(anchor - timedelta(seconds=5)), anchor)
        t = anchor + timedelta(seconds=33)
        self.assertEqual(trigger.next_after(t), anchor + timedelta(seconds=40))


if __name__ == "__main__":
    unittest.main()
