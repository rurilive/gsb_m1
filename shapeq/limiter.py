"""按 key 计数的固定窗口限流。

每个 key 独立计数，同一窗口内的请求共享同一份配额；窗口
按注入时钟对齐到 window 的整数倍，跨窗口自动重新计数。
"""

import threading
import time


class FixedWindowLimiter:
    """固定窗口计数限流器。

    limit: 单个窗口内允许放行的请求数。
    window: 窗口长度（秒），必须为正。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, limit, window, clock=time.monotonic):
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if window <= 0:
            raise ValueError("window must be > 0")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._lock = threading.Lock()
        # key -> [window_index, count_in_window]
        self._buckets = {}
        self._allowed = 0
        self._rejected = 0

    def allow(self, key):
        """放行则返回 True 并占掉一个名额，超限返回 False。"""
        with self._lock:
            index = int(self._clock() // self._window)
            state = self._buckets.get(key)
            if state is None or state[0] != index:
                state = [index, 0]
                self._buckets[key] = state
            if state[1] >= self._limit:
                self._rejected += 1
                return False
            state[1] += 1
            self._allowed += 1
            return True

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "allowed": self._allowed,
                "rejected": self._rejected,
                "keys": len(self._buckets),
            }
