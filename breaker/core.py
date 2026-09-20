"""依赖保护的熔断器。

三态实现：closed、open 与 half-open。连续失败达到阈值进入 open，
冷却结束后进入 half-open 只放行少量探测；探测成功累计达标回到
closed，任一探测失败立即回到 open 并按抖动公式重新计时。时钟
与随机源均通过构造参数注入，方便测试与业务侧替换。
"""

import random
import threading
import time


class CircuitBreaker:
    """连续失败计数的三态熔断器。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

    HALF_OPEN_MAX_PROBES = 3
    HALF_OPEN_SUCCESS_THRESHOLD = 2

    def __init__(self, threshold=5, cooldown=30.0, clock=time.monotonic,
                 r=random.random):
        self._threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._r = r
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._current_cooldown = cooldown
        self._half_open_issued = 0
        self._half_open_successes = 0

    def allow_request(self):
        """当前是否放行请求。half-open 下每次放行占用一个探测名额。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return False
            if self._state == self.HALF_OPEN:
                if self._half_open_issued >= self.HALF_OPEN_MAX_PROBES:
                    return False
                self._half_open_issued += 1
            return True

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
            if self._state == self.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.HALF_OPEN_SUCCESS_THRESHOLD:
                    self._close()
                return
            self._consecutive_failures = 0

    def record_failure(self):
        """上报一次失败。连续失败达到阈值即熔断；半开探测失败立即重开。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return
            if self._state == self.HALF_OPEN:
                self._trip(jitter=True)
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold:
                self._trip(jitter=False)

    def _trip(self, jitter):
        self._state = self.OPEN
        self._opened_at = self._clock()
        self._consecutive_failures = 0
        if jitter:
            self._current_cooldown = self._cooldown * (0.8 + 0.4 * self._r())
        else:
            self._current_cooldown = self._cooldown
        self._half_open_issued = 0
        self._half_open_successes = 0

    def _close(self):
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._half_open_issued = 0
        self._half_open_successes = 0

    def _refresh(self):
        """冷却期满时把 open 拉回 half-open（惰性转移）。"""
        if (
            self._state == self.OPEN
            and self._clock() - self._opened_at >= self._current_cooldown
        ):
            self._state = self.HALF_OPEN
            self._half_open_issued = 0
            self._half_open_successes = 0
