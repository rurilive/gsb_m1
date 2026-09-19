"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标。默认样本永久保留；配置
window_seconds 后只统计滑动窗口内的样本。
"""

import bisect
import threading
import time


class Histogram:
    """直方图：observe 记样本，percentiles 取分位，可选滑动窗口。"""

    def __init__(self, window_seconds=None, clock=None):
        self._lock = threading.Lock()
        self._samples = []  # (timestamp, value)
        self._window = window_seconds
        self._clock = clock if clock is not None else time.monotonic

    def observe(self, value):
        """记录一个样本，返回本次被挤出窗口的样本数（无窗口时恒为 0）。"""
        with self._lock:
            evicted = self._purge_locked()
            self._samples.append((self._clock(), value))
            return evicted

    def count(self):
        """当前窗口内样本总数。"""
        with self._lock:
            self._purge_locked()
            return len(self._samples)

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。无样本抛 ValueError。"""
        with self._lock:
            self._purge_locked()
            if not self._samples:
                raise ValueError("no samples")
            data = sorted(v for _, v in self._samples)
        return {p: _interpolate(data, p) for p in fractions}

    def compact(self):
        """显式清理过期样本，返回清理数。"""
        with self._lock:
            return self._purge_locked()

    def snapshot(self, bucket_edges):
        """按严格递增边界导出窗口内分桶计数；值等于边界归右桶。"""
        edges = list(bucket_edges)
        if any(edges[i] >= edges[i + 1] for i in range(len(edges) - 1)):
            raise ValueError("bucket_edges must be strictly increasing")
        with self._lock:
            self._purge_locked()
            values = [v for _, v in self._samples]
        buckets = [0] * (len(edges) + 1)
        for v in values:
            buckets[bisect.bisect_right(edges, v)] += 1
        return buckets

    def _purge_locked(self):
        """剔除过期样本（now - t > window），返回剔除数。"""
        if self._window is None:
            return 0
        cutoff = self._clock() - self._window
        kept = [(t, v) for t, v in self._samples if t >= cutoff]
        evicted = len(self._samples) - len(kept)
        self._samples = kept
        return evicted


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
