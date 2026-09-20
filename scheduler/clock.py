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

    def wait(self, seconds: float, stop: "threading.Event | None" = None) -> bool:
        """等待 seconds（由时钟实现定义"经过"的含义），stop 置位时提前返回。

        返回 True 表示等待被 stop 提前打断。
        """
        if stop is None:
            self.sleep(seconds)
            return False
        deadline = _time.monotonic() + seconds
        while not stop.is_set():
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                return False
            if stop.wait(timeout=min(remaining, 0.05)):
                return True
        return True


class SystemClock(Clock):

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        _time.sleep(seconds)


class FakeClock(Clock):
    """手动推进的时钟。sleep()/wait() 阻塞到时钟越过目标时刻（由测试线程 advance 唤醒）。"""

    def __init__(self, start: datetime):
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        self._cond = threading.Condition()
        self._now = start
        self._waiters = 0

    def now(self) -> datetime:
        with self._cond:
            return self._now

    def sleep(self, seconds: float) -> None:
        self.wait(seconds)

    def wait_until_waiting(self, timeout: float = 5.0) -> bool:
        """阻塞到至少有一个线程挂在 wait()/sleep() 上（测试同步用）。"""
        deadline = _time.monotonic() + timeout
        with self._cond:
            while self._waiters == 0 and _time.monotonic() < deadline:
                self._cond.wait(timeout=0.01)
            return self._waiters > 0

    def wait(self, seconds: float, stop: "threading.Event | None" = None) -> bool:
        with self._cond:
            target = self._now + timedelta(seconds=seconds)
            self._waiters += 1
            self._cond.notify_all()
            try:
                self._cond.wait_for(
                    lambda: self._now >= target or (stop is not None and stop.is_set()))
            finally:
                self._waiters -= 1
                self._cond.notify_all()
            return stop is not None and stop.is_set() and self._now < target

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

    def interrupt(self) -> None:
        """唤醒所有等待者（等价于外部中断事件被置位后的通知）。"""
        with self._cond:
            self._cond.notify_all()
