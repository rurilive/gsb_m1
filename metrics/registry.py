"""进程内指标注册表：counter/gauge 按名字注册，带标签维度，支持快照导出。"""
import threading

__all__ = [
    "Registry",
    "Counter",
    "Gauge",
    "DuplicateMetric",
    "OVERFLOW_LABEL",
    "DEFAULT_MAX_SERIES",
]

#: 单个指标默认允许的最大序列数，超限的新序列进入兜底桶
DEFAULT_MAX_SERIES = 10_000

#: 兜底桶序列的标签值，snapshot 中以此标识被合并的溢出序列
OVERFLOW_LABEL = "__overflow__"

#: snapshot 中保留的被丢维度采样条数上限，防止观测数据本身撑爆内存
_DROPPED_KEYS_SAMPLE = 128


class DuplicateMetric(KeyError):
    """同名指标重复注册。"""


def _key(labels, label_names):
    # 按注册时声明的标签名顺序取值，未提供的维度记为空串
    return tuple(str(labels.get(name, "")) for name in label_names)


class _Metric:
    kind = "metric"

    def __init__(self, name, label_names, max_series=DEFAULT_MAX_SERIES):
        if max_series < 1:
            raise ValueError("max_series must be >= 1")
        self.name = name
        self.label_names = tuple(label_names)
        self.max_series = max_series
        self._lock = threading.Lock()
        self._series = {}
        self._overflow = None
        self._dropped_writes = 0
        self._dropped_keys = []
        self._dropped_keys_truncated = False

    def _bump(self, key, amount):
        raise NotImplementedError

    def _has_room(self):
        return len(self._series) < self.max_series

    def _note_dropped(self, key):
        self._dropped_writes += 1
        if len(self._dropped_keys) < _DROPPED_KEYS_SAMPLE:
            labels = dict(zip(self.label_names, key))
            if labels not in self._dropped_keys:
                self._dropped_keys.append(labels)
        else:
            self._dropped_keys_truncated = True

    def reset(self):
        """清空全部序列与溢出状态；被丢维度下次写入即回到正常序列重新起算。"""
        with self._lock:
            self._series.clear()
            self._overflow = None
            self._dropped_writes = 0
            self._dropped_keys = []
            self._dropped_keys_truncated = False

    def snapshot(self):
        with self._lock:
            items = sorted(self._series.items())
            overflow = self._overflow
            dropped_writes = self._dropped_writes
            dropped_keys = [dict(labels) for labels in self._dropped_keys]
            dropped_keys_truncated = self._dropped_keys_truncated
        series = [
            {"labels": dict(zip(self.label_names, key)), "value": value}
            for key, value in items
        ]
        if overflow is not None:
            series.append(
                {
                    "labels": {name: OVERFLOW_LABEL for name in self.label_names},
                    "value": overflow,
                }
            )
        return {
            "name": self.name,
            "type": self.kind,
            "label_names": list(self.label_names),
            "series": series,
            "cardinality": {
                "max_series": self.max_series,
                "active_series": len(items),
                "dropped_writes": dropped_writes,
                "dropped_keys": dropped_keys,
                "dropped_keys_truncated": dropped_keys_truncated,
            },
        }


class Counter(_Metric):
    """单调递增计数器，每个标签组合是一条独立序列。"""

    kind = "counter"

    def inc(self, amount=1, **labels):
        key = _key(labels, self.label_names)
        with self._lock:
            if key in self._series or self._has_room():
                self._series[key] = self._series.get(key, 0) + amount
            else:
                base = self._overflow if self._overflow is not None else 0
                self._overflow = base + amount
                self._note_dropped(key)

    def value(self, **labels):
        return self._series.get(_key(labels, self.label_names), 0)


class Gauge(_Metric):
    """可增可减的瞬时值，每个标签组合是一条独立序列。"""

    kind = "gauge"

    def set(self, value, **labels):
        key = _key(labels, self.label_names)
        with self._lock:
            if key in self._series or self._has_room():
                self._series[key] = value
            else:
                self._overflow = value
                self._note_dropped(key)

    def value(self, **labels):
        return self._series.get(_key(labels, self.label_names))


class Registry:
    """指标注册表，全局按名字唯一。"""

    def __init__(self, max_series=DEFAULT_MAX_SERIES):
        self._max_series = max_series
        self._lock = threading.Lock()
        self._metrics = {}

    def _register(self, metric):
        with self._lock:
            if metric.name in self._metrics:
                raise DuplicateMetric(metric.name)
            self._metrics[metric.name] = metric
        return metric

    def _limit(self, max_series):
        return self._max_series if max_series is None else max_series

    def counter(self, name, label_names=(), max_series=None):
        return self._register(Counter(name, label_names, self._limit(max_series)))

    def gauge(self, name, label_names=(), max_series=None):
        return self._register(Gauge(name, label_names, self._limit(max_series)))

    def get(self, name):
        return self._metrics[name]

    def snapshot(self):
        with self._lock:
            metrics = sorted(self._metrics.values(), key=lambda m: m.name)
        return {"metrics": [metric.snapshot() for metric in metrics]}
