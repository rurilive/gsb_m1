"""触发器防回归测试：墙钟语义、夏令时跳变、短月跳过。"""
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scheduler import DailyTrigger, IntervalTrigger, MonthlyTrigger

UTC = timezone.utc
BERLIN = ZoneInfo("Europe/Berlin")
SHANGHAI = ZoneInfo("Asia/Shanghai")


class DailyTriggerDSTTest(unittest.TestCase):
    # 现象 1：柏林 09:30 巡检，夏令时切换当天不能晚 1 小时，次日起恢复正常。

    def test_spring_forward_stays_on_wall_clock(self):
        # 2026-03-29 02:00 欧洲进入夏令时（CET+1 -> CEST+2）。
        trig = DailyTrigger(9, 30, "Europe/Berlin")
        sat = datetime(2026, 3, 28, 9, 30, tzinfo=BERLIN)
        sun = trig.next_after(sat.astimezone(UTC))
        mon = trig.next_after(sun)
        self.assertEqual(sun.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M%z"),
                         "2026-03-29 09:30+0200")
        self.assertEqual(mon.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M%z"),
                         "2026-03-30 09:30+0200")

    def test_fall_back_stays_on_wall_clock(self):
        # 2026-10-25 03:00 欧洲回到冬令时，当天墙钟间隔 25 小时。
        trig = DailyTrigger(9, 30, "Europe/Berlin")
        sat = datetime(2026, 10, 24, 9, 30, tzinfo=BERLIN)
        sun = trig.next_after(sat.astimezone(UTC))
        mon = trig.next_after(sun)
        self.assertEqual(sun.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M%z"),
                         "2026-10-25 09:30+0100")
        self.assertEqual(mon.astimezone(BERLIN).strftime("%Y-%m-%d %H:%M%z"),
                         "2026-10-26 09:30+0100")

    def test_non_transition_days_unaffected(self):
        trig = DailyTrigger(9, 30, "Europe/Berlin")
        cur = datetime(2026, 6, 1, 9, 30, tzinfo=BERLIN).astimezone(UTC)
        for day in range(2, 8):
            cur = trig.next_after(cur)
            local = cur.astimezone(BERLIN)
            self.assertEqual((local.hour, local.minute), (9, 30))
            self.assertEqual(local.day, day)


class MonthlyTriggerTest(unittest.TestCase):
    # 现象 4：每月 31 号在 2 月必须整月跳过，不能在 2 月 28 号触发。

    def test_day31_skips_february_and_short_months(self):
        trig = MonthlyTrigger(31, 8, 0, "Asia/Shanghai")
        cur = datetime(2026, 1, 31, 8, 0, tzinfo=SHANGHAI).astimezone(UTC)
        fired = []
        for _ in range(7):
            cur = trig.next_after(cur)
            fired.append(cur.astimezone(SHANGHAI))
        months = [(d.year, d.month, d.day) for d in fired]
        self.assertNotIn((2026, 2, 28), months)
        self.assertEqual(months, [
            (2026, 3, 31), (2026, 5, 31), (2026, 7, 31),
            (2026, 8, 31), (2026, 10, 31), (2026, 12, 31),
            (2027, 1, 31),
        ])
        for d in fired:
            self.assertEqual((d.hour, d.minute), (8, 0))

    def test_day15_fires_every_month(self):
        trig = MonthlyTrigger(15, 8, 0, "Asia/Shanghai")
        cur = datetime(2026, 1, 15, 8, 0, tzinfo=SHANGHAI).astimezone(UTC)
        months = []
        for _ in range(3):
            cur = trig.next_after(cur)
            months.append((cur.astimezone(SHANGHAI).month,
                           cur.astimezone(SHANGHAI).day))
        self.assertEqual(months, [(2, 15), (3, 15), (4, 15)])

    def test_day31_keeps_wall_clock_across_berlin_dst(self):
        # 1 月（CET+1）→ 3 月 31 日（CEST+2），墙钟必须始终是 08:00。
        trig = MonthlyTrigger(31, 8, 0, "Europe/Berlin")
        cur = datetime(2026, 1, 31, 8, 0, tzinfo=BERLIN).astimezone(UTC)
        nxt = trig.next_after(cur).astimezone(BERLIN)
        self.assertEqual(nxt.replace(tzinfo=None),
                         datetime(2026, 3, 31, 8, 0))
        self.assertEqual(nxt.utcoffset(), timedelta(hours=2))


class IntervalTriggerTest(unittest.TestCase):

    def test_anchor_grid_and_strictly_after(self):
        anchor = datetime(2026, 1, 1, tzinfo=UTC)
        trig = IntervalTrigger(timedelta(minutes=10), anchor=anchor)
        self.assertEqual(trig.next_after(anchor),
                         anchor + timedelta(minutes=10))
        self.assertEqual(trig.next_after(anchor + timedelta(minutes=10, seconds=1)),
                         anchor + timedelta(minutes=20))


if __name__ == "__main__":
    unittest.main()
