"""时钟抽象：时间读取与等待统一走 Clock，便于测试注入。"""
import threading
import time as _time
from abc import ABC, abstractmethod


class Clock(ABC):

    @abstractmethod
    def time(self) -> float:
        """返回当前时刻（秒）。"""

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        """阻塞 seconds 秒。"""


class SystemClock(Clock):
    """进程默认时钟。

    使用单调时钟（monotonic），不受 NTP 校时/墙钟回拨影响，
    保证限流补充逻辑看到的时间永不倒退。
    """

    def time(self) -> float:
        return _time.monotonic()

    def sleep(self, seconds: float) -> None:
        _time.sleep(seconds)


class FakeClock(Clock):
    """手动推进的时钟，测试用。"""

    def __init__(self, start: float = 0.0):
        self._now = float(start)
        self._lock = threading.Lock()

    def time(self) -> float:
        with self._lock:
            return self._now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self._now += max(0.0, seconds)

    def advance(self, seconds: float) -> None:
        """向前拨 seconds 秒。"""
        with self._lock:
            self._now += seconds

    def jump_to(self, moment: float) -> None:
        """直接跳到某个时刻（可往前也可往后）。"""
        with self._lock:
            self._now = float(moment)
