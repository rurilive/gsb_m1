"""breaker: 依赖保护的熔断器。"""
"""依赖保护的熔断器。

三态实现：closed / open / half-open。连续失败达到阈值进入 open；
冷却期满后进 half-open，只放行固定名额的探测请求；探测成功累计
满次数回到 closed，任一探测失败立即回 open 并重新计时。

时钟 clock 与随机源 rand 均通过构造参数注入，方便测试与业务侧替换。
"""

import random
import threading
import time


class CircuitBreaker:
    """连续失败计数的三态熔断器。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    PROBE_PERMITS = 3    # half-open 探测名额（固定）
    PROBE_SUCCESSES = 2  # half-open 闭合所需的探测成功次数（固定）

    def __init__(self, threshold=5, cooldown=30.0, clock=time.monotonic,
                 rand=random.random):
        self._threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._rand = rand
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._current_cooldown = cooldown
        self._probe_permits_left = 0
        self._probe_successes = 0

    def allow_request(self):
        """当前是否放行请求。half-open 下只在探测名额内放行。"""
        with self._lock:
            self._refresh()
            if self._state == self.OPEN:
                return False
            if self._state == self.HALF_OPEN:
                if self._probe_permits_left <= 0:
                    return False
                self._probe_permits_left -= 1
                return True
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
                self._probe_successes += 1
                if self._probe_successes >= self.PROBE_SUCCESSES:
                    self._close()
                return
            self._consecutive_failures = 0

    def record_failure(self):
        """上报一次失败。连续失败达到阈值即熔断；探测失败立即回 open。"""
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

    def _close(self):
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._probe_permits_left = 0
        self._probe_successes = 0

    def _trip(self, jitter):
        self._state = self.OPEN
        self._opened_at = self._clock()
        self._consecutive_failures = 0
        self._probe_permits_left = 0
        self._probe_successes = 0
        if jitter:
            # 半开探测失败回 open：本次冷却加伪随机抖动，避免震荡时整簇重试。
            self._current_cooldown = self._cooldown * (0.8 + 0.4 * self._rand())
        else:
            # 首次熔断按基础冷却计时，行为确定。
            self._current_cooldown = self._cooldown

    def _refresh(self):
        """冷却期满时把 open 推进到 half-open（惰性转移），并重发探测名额。"""
        if (
            self._state == self.OPEN
            and self._clock() - self._opened_at >= self._current_cooldown
        ):
            self._state = self.HALF_OPEN
            self._probe_permits_left = self.PROBE_PERMITS
            self._probe_successes = 0
