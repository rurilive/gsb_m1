"""依赖保护的熔断器。

三态实现：closed / open / half-open。连续失败达到阈值进入
open，冷却期满后不直接闭合，而是进入 half-open 只放行固定
数量的探测请求；探测累计成功满 2 次回到 closed，任一失败
立即回 open 并按抖动后的冷却重新计时。时钟 clock 与随机源
random 均可构造注入，方便测试与业务侧替换。
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
        """是否放行请求；half-open 下放行即占用一个探测名额。"""
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
        """上报一次成功。半开下累计满 2 次闭合，open 下忽略。"""
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
        """进入 open：首次熔断用基础冷却，半开失败重开抽抖动。"""
        self._state = self.OPEN
        self._opened_at = self._clock()
        if jitter:
            self._current_cooldown = self._cooldown * (
                0.8 + 0.4 * self._random()
            )
        else:
            self._current_cooldown = self._cooldown
        self._consecutive_failures = 0
        self._probe_slots = 0
        self._probe_successes = 0

    def _close(self):
        """回到 closed 并清零全部计数。"""
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
