"""线程安全的数值直方图。

默认样本永久保留；配置 window_seconds 后改为滑动窗口，
只有窗口内样本参与 count/percentiles/snapshot。时钟可注入，
默认用 time.monotonic。锁保护全部读写。
"""

import bisect
import time
import threading
from collections import deque


class Histogram:
    """线程安全直方图：observe 记样本，percentiles 取分位。

    window_seconds=None 时样本永久保留，行为与全量直方图一致；
    配置窗口后按 clock() 的时间戳只保留近 window_seconds 秒的样本，
    恰满 window_seconds（时间戳恰在边界上）的样本仍算窗口内。
    """

    def __init__(self, window_seconds=None, clock=None):
        if window_seconds is not None and window_seconds < 0:
            raise ValueError("window_seconds must be non-negative")
        self._lock = threading.Lock()
        self._window = window_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._values = []
        self._timed = deque()

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数（无窗口恒为 0）。"""
        with self._lock:
            if self._window is None:
                self._values.append(value)
                return 0
            evicted = self._evict_locked()
            self._timed.append((self._clock(), value))
            return evicted

    def count(self):
        """窗口内样本总数（无窗口时为全量总数）。"""
        with self._lock:
            if self._window is None:
                return len(self._values)
            return len(self._active_locked())

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。窗口内无样本抛 ValueError。"""
        with self._lock:
            if self._window is None:
                data = sorted(self._values)
            else:
                data = sorted(self._active_locked())
        if not data:
            raise ValueError("no samples")
        return {p: _interpolate(data, p) for p in fractions}

    def compact(self):
        """物理清理已滑出窗口的旧样本，返回清理数（无窗口恒为 0）。"""
        with self._lock:
            if self._window is None:
                return 0
            return self._evict_locked()

    def snapshot(self, bucket_edges):
        """按严格递增边界导出窗口内分桶计数，值等于边界归右桶。

        返回长度为 len(bucket_edges) + 1 的 list：第 0 桶是小于最小
        边界的值，第 i 桶是 [edge_i-1, edge_i)，末桶是大于等于最大
        边界的值。值恰等于边界时归入右侧桶。
        """
        edges = list(bucket_edges)
        if any(edges[i] >= edges[i + 1] for i in range(len(edges) - 1)):
            raise ValueError("bucket_edges must be strictly increasing")
        counts = [0] * (len(edges) + 1)
        with self._lock:
            if self._window is None:
                values = self._values
            else:
                values = self._active_locked()
            for value in values:
                counts[bisect.bisect_right(edges, value)] += 1
        return counts

    def _evict_locked(self):
        """删除并返回早于窗口边界的样本数。"""
        cutoff = self._clock() - self._window
        removed = 0
        while self._timed and self._timed[0][0] < cutoff:
            self._timed.popleft()
            removed += 1
        return removed

    def _active_locked(self):
        """返回窗口内样本值列表（惰性判定，不物理删除）。"""
        cutoff = self._clock() - self._window
        return [value for ts, value in self._timed if ts >= cutoff]


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
