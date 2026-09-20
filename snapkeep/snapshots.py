"""对象状态快照的暂存与按时刻读取。

每个对象维持一串带时间戳的快照，内部按时间升序保存；读取时
取「不晚于给定时刻」的最近一张。纯标准库。
"""

import bisect
import threading
import time


class SnapshotStore:
    """按对象保存快照序列。

    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic，
    测试可注入假时钟来精确控制时间轴。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # obj -> [[ts, state], ...]，ts 升序
        self._snaps = {}

    def take(self, obj, state):
        """给 obj 存一张当前时刻的快照，返回该快照的时间戳。"""
        with self._lock:
            ts = self._clock()
            self._snaps.setdefault(obj, []).append([ts, state])
            return ts

    def get(self, obj, ts):
        """取 obj 在 ts 时刻的状态：不晚于 ts 的最近一张快照。

        该对象没有任何不晚于 ts 的快照时返回 None。
        """
        with self._lock:
            snaps = self._snaps.get(obj)
            if not snaps:
                return None
            times = [s[0] for s in snaps]
            i = bisect.bisect_right(times, ts) - 1
            if i < 0:
                return None
            return snaps[i][1]

    def list(self, obj):
        """返回 obj 全部快照的时间戳，升序；没有快照时返回空列表。"""
        with self._lock:
            snaps = self._snaps.get(obj)
            if not snaps:
                return []
            return [s[0] for s in snaps]
