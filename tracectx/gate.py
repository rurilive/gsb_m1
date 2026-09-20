"""并发上限闸门：限制同时进入临界区的线程数，其余排队等待。"""

import threading


class Gate:
    """最多 max_active 个线程同时通过。

    enter 阻塞直到拿到名额（timeout 秒拿不到抛 TimeoutError）；
    leave 归还名额。也可当上下文管理器用（不支持超时）。
    """

    def __init__(self, max_active):
        if max_active < 1:
            raise ValueError("max_active must be >= 1")
        self._max_active = max_active
        self._sem = threading.BoundedSemaphore(max_active)
        self._lock = threading.Lock()
        self._active = 0

    @property
    def max_active(self):
        return self._max_active

    @property
    def active(self):
        """当前在临界区内的线程数。"""
        with self._lock:
            return self._active

    def enter(self, timeout=None):
        """拿一个名额，阻塞直到成功或超时。"""
        if not self._sem.acquire(timeout=timeout):
            raise TimeoutError("gate busy for %ss" % timeout)
        with self._lock:
            self._active += 1

    def leave(self):
        """归还一个名额。多还抛 ValueError（BoundedSemaphore 兜底）。"""
        with self._lock:
            self._active -= 1
        self._sem.release()

    def __enter__(self):
        self.enter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.leave()
