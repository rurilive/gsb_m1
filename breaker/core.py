"""依赖保护的熔断器。

三态实现：closed / open / half-open。连续失败达到阈值进入
open，冷却 cooldown*抖动 秒后进入 half-open 只放行探测请求；
探测累计成功若干次后回到 closed，任一失败立即回 open 重新计时。
时钟与随机源均可构造注入，方便测试与业务侧替换。
"""

import random
import threading
import time


class CircuitBreaker:
    """带半开探测的三态熔断器。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    HALF_OPEN_MAX_PROBES = 3
    HALF_OPEN_SUCCESS_TO_CLOSE = 2

    def __init__(
        self,
        threshold=5,
        cooldown=30.0,
        clock=time.monotonic,
        random=random.random,
    ):
        self._threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._random = random
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._current_cooldown = self._cooldown
        self._probe_slots = 0
        self._probe_successes = 0

    def allow_request(self):
        """当前是否放行请求，放行者占用一个半开探测名额。"""
        with self._lock:
            self._refresh()
            if self._state == self.CLOSED:
                return True
            if (
                self._state == self.HALF_OPEN
                and self._probe_slots < self.HALF_OPEN_MAX_PROBES
            ):
                self._probe_slots += 1
                return True
            return False

    def is_open(self):
        """是否处于断开状态。"""
        with self._lock:
            self._refresh()
            return self._state == self.OPEN

    @property
    def state(self):
        """当前状态（closed / open / half_open）。"""
        with self._lock:
            self._refresh()
            return self._state

    def record_success(self):
        """上报一次成功。半开下累计成功满额闭合，open 下忽略。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return
            if self._state == self.HALF_OPEN:
                if self._probe_slots > 0:
                    self._probe_slots -= 1
                self._probe_successes += 1
                if self._probe_successes >= self.HALF_OPEN_SUCCESS_TO_CLOSE:
                    self._close()
                return
            self._consecutive_failures = 0

    def record_failure(self):
        """上报一次失败。连续失败达阈值熔断，半开下立即回 open。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return
            if self._state == self.HALF_OPEN:
                self._trip(jitter=True)
                return
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._threshold:
                self._trip()

    def _trip(self, jitter=False):
        self._state = self.OPEN
        self._opened_at = self._clock()
        if jitter:
            self._current_cooldown = self._cooldown * (0.8 + 0.4 * self._random())
        else:
            self._current_cooldown = self._cooldown
        self._consecutive_failures = 0
        self._probe_slots = 0
        self._probe_successes = 0

    def _close(self):
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._probe_slots = 0
        self._probe_successes = 0

    def _refresh(self):
        """冷却期满时把 open 拉回 half-open（惰性转移）。"""
        if (
            self._state == self.OPEN
            and self._clock() - self._opened_at >= self._current_cooldown
        ):
            self._state = self.HALF_OPEN
            self._probe_slots = 0
            self._probe_successes = 0
