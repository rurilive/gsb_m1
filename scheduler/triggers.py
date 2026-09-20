"""触发器：决定任务的下一次触发时刻。所有时刻以 UTC 表示。"""
import calendar
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _wall_time(tz: ZoneInfo, year: int, month: int, day: int,
               hour: int, minute: int) -> datetime:
    """构造 tz 下的墙钟时刻并转为 UTC，正确处理夏令时间隙（不存在的时刻）。

    春季跳变日若目标时刻落在被跳过的小时内，顺延到间隙结束后的等价时刻；
    秋季回退的歧义时刻取第一次出现（fold=0）。
    """
    naive = datetime(year, month, day, hour, minute)
    aware = naive.replace(tzinfo=tz)
    utc = aware.astimezone(timezone.utc)
    if utc.astimezone(tz).replace(tzinfo=None) != naive:
        utc = (naive + timedelta(hours=1)).replace(tzinfo=tz).astimezone(timezone.utc)
    return utc


class Trigger(ABC):

    @abstractmethod
    def next_after(self, t: datetime) -> datetime:
        """返回严格晚于 t 的下一次触发时刻（UTC）。"""


class IntervalTrigger(Trigger):
    """固定间隔触发，锚定 anchor 网格：fire 序列恒为 anchor + n*interval，不随执行耗时漂移。"""

    def __init__(self, interval: timedelta, anchor: datetime | None = None):
        assert interval.total_seconds() > 0, "interval 必须为正"
        self.interval = interval
        self.anchor = _to_utc(anchor) if anchor is not None else _to_utc(datetime(2026, 1, 1))

    def next_after(self, t: datetime) -> datetime:
        t = _to_utc(t)
        step_us = self.interval // timedelta(microseconds=1)
        delta_us = (t - self.anchor) // timedelta(microseconds=1)
        n = delta_us // step_us + 1
        return self.anchor + timedelta(microseconds=n * step_us)


class DailyTrigger(Trigger):
    """每天 tz 时区墙钟 hour:minute 触发，跟随墙钟（含夏令时跳变日）。"""

    def __init__(self, hour: int, minute: int, tz: str = "Asia/Shanghai"):
        assert 0 <= hour <= 23 and 0 <= minute <= 59
        self.hour, self.minute = hour, minute
        self.tz = ZoneInfo(tz)

    def next_after(self, t: datetime) -> datetime:
        t = _to_utc(t)
        local = t.astimezone(self.tz)
        nxt = local.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if nxt <= local:
            nxt = nxt + timedelta(days=1)
        return _wall_time(self.tz, nxt.year, nxt.month, nxt.day,
                          nxt.hour, nxt.minute)


class MonthlyTrigger(Trigger):
    """每月 day 号的 hour:minute 触发。短月没有该号（如 2 月 31 日）则整月跳过，
    顺延到下一个存在的月份，与 crontab 的 day-of-month 语义一致。"""

    def __init__(self, day: int, hour: int, minute: int, tz: str = "Asia/Shanghai"):
        assert 1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59
        self.day, self.hour, self.minute = day, hour, minute
        self.tz = ZoneInfo(tz)

    def next_after(self, t: datetime) -> datetime:
        t = _to_utc(t)
        local = t.astimezone(self.tz)
        y, m = local.year, local.month
        while True:
            last = calendar.monthrange(y, m)[1]
            if self.day <= last:
                cand = local.replace(year=y, month=m, day=self.day,
                                     hour=self.hour, minute=self.minute,
                                     second=0, microsecond=0)
                if cand > local:
                    return _wall_time(self.tz, y, m, self.day,
                                      self.hour, self.minute)
            m += 1
            if m == 13:
                m, y = 1, y + 1
