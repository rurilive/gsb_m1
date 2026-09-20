"""进程内指标注册表：counter/gauge 按名字注册，带标签维度，支持快照导出。

基数控制：每个指标可设 max_series（注册表可给默认值）。超限的新维度
不拒绝写入，而是并入兜底桶 __overflow__，并记录被打掉的维度样本；
序列数回落（reset 后）时被打掉的维度自动恢复为独立序列，兜底桶旧值保留。
"""
import threading

__all__ = ["Registry", "Counter", "Gauge", "DuplicateMetric"]

OVERFLOW_LABEL = "__overflow__"
_DROPPED_SAMPLE_MAX = 128


class DuplicateMetric(KeyError):
    """同名指标重复注册。"""


def _key(labels, label_names):
    # 按注册时声明的标签名顺序取值，未提供的维度记为空串
    return tuple(str(labels.get(name, "")) for name in label_names)


class _Metric:
    kind = "metric"

    def __init__(self, name, label_names, max_series=None):
        self.name = name
        self.label_names = tuple(label_names)
        self.max_series = max_series
        self._lock = threading.Lock()
        self._series = {}
        self._overflow = None  # 兜底桶累计值
        self._dropped = {}     # 被打掉的维度 key -> 被并入兜底桶的次数（有界样本）
        self._dropped_writes = 0

    def _combine(self, a, b):
        raise NotImplementedError

    def _write(self, key, amount):
        with self._lock:
            if key in self._series:
                self._series[key] = self._combine(self._series[key], amount)
                return
            if self.max_series is None or len(self._series) < self.max_series:
                self._dropped.pop(key, None)  # 有位置，恢复为独立序列
                self._series[key] = self._combine(None, amount)
                return
            # 超限：不丢数据，并入兜底桶，记录维度样本
            self._overflow = self._combine(self._overflow, amount)
            self._dropped_writes += 1
            if key in self._dropped:
                self._dropped[key] += 1
            elif len(self._dropped) < _DROPPED_SAMPLE_MAX:
                self._dropped[key] = 1

    def reset(self):
        """清空活跃序列（兜底桶与统计保留，供观测；被打掉的维度之后可恢复）。"""
        with self._lock:
            self._series.clear()

    def snapshot(self):
        with self._lock:
            items = sorted(self._series.items())
            overflow = self._overflow
            dropped = sorted(self._dropped.items())
            dropped_writes = self._dropped_writes
            limit = self.max_series
            size = len(self._series)
        series = [
            {"labels": dict(zip(self.label_names, key)), "value": value}
            for key, value in items
        ]
        if overflow is not None:
            series.append({
                "labels": {name: OVERFLOW_LABEL for name in self.label_names},
                "value": overflow,
            })
        snap = {
            "name": self.name,
            "type": self.kind,
            "label_names": list(self.label_names),
            "series": series,
        }
        if limit is not None:
            snap["cardinality"] = {
                "limit": limit,
                "series": size,
                "overflowed": overflow is not None,
                "dropped_writes": dropped_writes,
                "dropped_keys": [
                    {"labels": dict(zip(self.label_names, key)), "writes": n}
                    for key, n in dropped
                ],
            }
        return snap


class Counter(_Metric):
    """单调递增计数器，每个标签组合是一条独立序列。"""

    kind = "counter"

    def _combine(self, old, amount):
        return (old or 0) + amount

    def inc(self, amount=1, **labels):
        self._write(_key(labels, self.label_names), amount)

    def value(self, **labels):
        return self._series.get(_key(labels, self.label_names), 0)


class Gauge(_Metric):
    """可增可减的瞬时值，每个标签组合是一条独立序列。"""

    kind = "gauge"

    def _combine(self, old, value):
        return value

    def set(self, value, **labels):
        self._write(_key(labels, self.label_names), value)

    def value(self, **labels):
        return self._series.get(_key(labels, self.label_names))


class Registry:
    """指标注册表，全局按名字唯一。"""

    def __init__(self, max_series=None):
        self._max_series = max_series
        self._lock = threading.Lock()
        self._metrics = {}

    def _register(self, metric):
        with self._lock:
            if metric.name in self._metrics:
                raise DuplicateMetric(metric.name)
            self._metrics[metric.name] = metric
        return metric

    def counter(self, name, label_names=(), max_series=None):
        limit = self._max_series if max_series is None else max_series
        return self._register(Counter(name, label_names, limit))

    def gauge(self, name, label_names=(), max_series=None):
        limit = self._max_series if max_series is None else max_series
        return self._register(Gauge(name, label_names, limit))

    def get(self, name):
        return self._metrics[name]

    def snapshot(self, series_budget=None):
        """全量导出。series_budget 限制本次导出的总序列条数，
        超出部分截断并在对应指标上标记 truncated，防止导出把内存顶爆。"""
        with self._lock:
            metrics = sorted(self._metrics.values(), key=lambda m: m.name)
        out = []
        remaining = series_budget
        for metric in metrics:
            snap = metric.snapshot()
            if remaining is not None:
                if remaining <= 0:
                    snap["series"] = []
                    snap["truncated"] = True
                elif len(snap["series"]) > remaining:
                    snap["series"] = snap["series"][:remaining]
                    snap["truncated"] = True
                remaining -= len(snap["series"])
            out.append(snap)
        return {"metrics": out}
