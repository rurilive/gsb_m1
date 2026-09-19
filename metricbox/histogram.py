"""线程安全的数值直方图。

样本存放在 list 里，锁保护全部读写。适合进程内聚合
P50/P95/P99 这类分位指标，样本永久保留。
"""

import threading


class Histogram:
    """全量样本的直方图：observe 记样本，percentiles 取分位。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._values = []

    def observe(self, value):
        """记录一个样本。"""
        with self._lock:
            self._values.append(value)

    def count(self):
        """当前样本总数。"""
        with self._lock:
            return len(self._values)

    def percentiles(self, *fractions):
        """返回 {分位: 值}，按 (n-1) 线性插值。无样本抛 ValueError。"""
        with self._lock:
            if not self._values:
                raise ValueError("no samples")
            data = sorted(self._values)
        return {p: _interpolate(data, p) for p in fractions}


def _interpolate(data, fraction):
    """有序样本上的线性插值分位。"""
    pos = fraction * (len(data) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(data) - 1)
    weight = pos - lo
    return data[lo] + (data[hi] - data[lo]) * weight
