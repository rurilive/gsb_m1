"""进程内事件指标聚合。

按事件时间累计计数，事件到达即入账，total() 汇总全部计数。
时钟从外部注入，纯标准库。
"""

import threading
import time


class EventCounter:
    """按事件时间累计计数。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # (ts, v) 按到达先后追加，暂不淘汰
        self._events = []
        self._total = 0.0
        self._last_arrival = None

    def add(self, ts, v=1):
        """记一个事件，ts 为事件时间，v 为计数增量，返回当前总和。

        事件时间不保证递增，乱序到达时原样入账。
        """
        with self._lock:
            self._events.append((ts, v))
            self._total += v
            self._last_arrival = self._clock()
            return self._total

    def total(self):
        """已记录事件的计数总和。"""
        with self._lock:
            return self._total

    def count(self):
        """已记录事件条数。"""
        with self._lock:
            return len(self._events)

    def span(self):
        """已记录事件的时间跨度 (最早, 最晚)，没有事件时返回 None。"""
        with self._lock:
            if not self._events:
                return None
            times = [ts for ts, _ in self._events]
            return (min(times), max(times))

    def last_arrival(self):
        """最近一次 add 的到达时刻，没有事件时返回 None。"""
        with self._lock:
            return self._last_arrival

    def reset(self):
        """清空全部事件与计数。"""
        with self._lock:
            self._events.clear()
            self._total = 0.0
            self._last_arrival = None
