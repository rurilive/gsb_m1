"""时钟抽象：所有时间读取与等待都必须走注入的 Clock，保证测试确定性。"""
import threading
import time as _time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone


class Clock(ABC):

    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    def sleep(self, seconds: float) -> None: ...


class SystemClock(Clock):

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        _time.sleep(seconds)


class FakeClock(Clock):
    """手动推进的时钟。sleep() 阻塞到时钟越过目标时刻（由测试线程 advance 唤醒）。"""

    _POLL = 0.02

    def __init__(self, start: datetime):
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        self._cond = threading.Condition()
        self._now = start

    def now(self) -> datetime:
        with self._cond:
            return self._now

    def sleep(self, seconds: float) -> None:
        with self._cond:
            target = self._now + timedelta(seconds=seconds)
            while self._now < target:
                self._cond.wait(timeout=self._POLL)

    def advance(self, seconds: float) -> None:
        with self._cond:
            self._now += timedelta(seconds=seconds)
            self._cond.notify_all()

    def jump_to(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        with self._cond:
            self._now = moment
            self._cond.notify_all()
