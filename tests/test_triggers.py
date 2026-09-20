"""触发器回归测试：夏令时墙钟跟随、每月触发短月跳过。"""
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scheduler.triggers import DailyTrigger, IntervalTrigger, MonthlyTrigger

BERLIN = ZoneInfo("Europe/Berlin")
SHANGHAI = ZoneInfo("Asia/Shanghai")


def local(y, m, d, hh=0, mm=0, tz=BERLIN):
    return datetime(y, m, d, hh, mm, tzinfo=tz).astimezone(timezone.utc)


class DailyTriggerTest(unittest.TestCase):

    def test_spring_forward_stays_on_wall_time(self):
        # 2026-03-29 柏林 02:00 -> 03:00，09:30 巡检在切换当天仍应是 09:30（UTC 提前一小时）。
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        before = local(2026, 3, 28, 12, 0)
        on_switch_day = trigger.next_after(before).astimezone(BERLIN)
        self.assertEqual((on_switch_day.month, on_switch_day.day), (3, 29))
        self.assertEqual((on_switch_day.hour, on_switch_day.minute), (9, 30))
        self.assertEqual(on_switch_day.utcoffset(), timedelta(hours=2))

    def test_day_after_switch_is_normal_again(self):
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        nxt = trigger.next_after(local(2026, 3, 28, 12, 0))
        following = trigger.next_after(nxt).astimezone(BERLIN)
        self.assertEqual((following.day, following.hour, following.minute), (30, 9, 30))

    def test_fall_back_stays_on_wall_time(self):
        # 2026-10-25 03:00 -> 02:00。当天 09:30 已在切换之后，偏移 +01:00，墙钟不变。
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        nxt = trigger.next_after(local(2026, 10, 24, 12, 0)).astimezone(BERLIN)
        self.assertEqual((nxt.day, nxt.hour, nxt.minute), (25, 9, 30))
        self.assertEqual(nxt.utcoffset(), timedelta(hours=1))

    def test_fall_back_ambiguous_time_first_occurrence(self):
        # 02:30 在回退日出现两次，fold=0 取第一次（+02:00）。
        trigger = DailyTrigger(2, 30, tz="Europe/Berlin")
        nxt = trigger.next_after(local(2026, 10, 24, 12, 0)).astimezone(BERLIN)
        self.assertEqual((nxt.day, nxt.hour, nxt.minute), (25, 2, 30))
        self.assertEqual(nxt.fold, 0)
        self.assertEqual(nxt.utcoffset(), timedelta(hours=2))

    def test_naive_input_treated_as_utc(self):
        trigger = DailyTrigger(9, 30, tz="Europe/Berlin")
        aware = trigger.next_after(datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc))
        naive = trigger.next_after(datetime(2026, 3, 28, 12, 0))
        self.assertEqual(aware, naive)


class MonthlyTriggerTest(unittest.TestCase):

    def test_day_31_skips_short_months(self):
        # 2026-01-31 之后：2 月、4 月、6 月都应整月跳过，不能钳成 28/30 号。
        trigger = MonthlyTrigger(31, 8, 0, tz="Asia/Shanghai")
        t = datetime(2026, 1, 31, 9, 0, tzinfo=SHANGHAI).astimezone(timezone.utc)
        fired = []
        for _ in range(4):
            t = trigger.next_after(t)
            fired.append(t.astimezone(SHANGHAI))
        self.assertEqual([(d.month, d.day, d.hour) for d in fired],
                         [(3, 31, 8), (5, 31, 8), (7, 31, 8), (8, 31, 8)])

    def test_day_15_fires_every_month(self):
        trigger = MonthlyTrigger(15, 8, 0, tz="Asia/Shanghai")
        t = datetime(2026, 1, 15, 9, 0, tzinfo=SHANGHAI).astimezone(timezone.utc)
        months = []
        for _ in range(3):
            t = trigger.next_after(t)
            months.append(t.astimezone(SHANGHAI).month)
        self.assertEqual(months, [2, 3, 4])


class IntervalTriggerTest(unittest.TestCase):

    def test_anchor_grid_no_drift(self):
        trigger = IntervalTrigger(timedelta(seconds=10))
        nxt = trigger.next_after(datetime(2026, 1, 1, 0, 0, 3, tzinfo=timezone.utc))
        self.assertEqual(nxt, datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
