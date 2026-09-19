"""依赖保护的熔断器。

目前是两态实现：closed 与 open。连续失败达到阈值进入 open，
冷却固定 cooldown 秒后回到 closed。时钟通过 clock 注入，
方便测试与业务侧替换。
"""

import threading
import time


class CircuitBreaker:
    """连续失败计数的两态熔断器。"""

    CLOSED = "closed"
    OPEN = "open"

    def __init__(self, threshold=5, cooldown=30.0, clock=time.monotonic):
        self._threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0

    def allow_request(self):
        """当前是否放行请求。"""
        with self._lock:
            self._refresh()
            return self._state != self.OPEN

    def is_open(self):
        """是否处于断开状态。"""
        with self._lock:
            self._refresh()
            return self._state == self.OPEN

    def record_success(self):
        """上报一次成功。熔断期间漏进来的零星成功不改变状态。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return
            self._consecutive_failures = 0

    def record_failure(self):
        """上报一次失败。连续失败达到阈值即熔断。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold:
                self._trip()

    def _trip(self):
        self._state = self.OPEN
        self._opened_at = self._clock()
        self._consecutive_failures = 0

    def _refresh(self):
        """冷却期满时把 open 拉回 closed（惰性转移）。"""
        if (
            self._state == self.OPEN
            and self._clock() - self._opened_at >= self._cooldown
        ):
            self._state = self.CLOSED
            self._consecutive_failures = 0
