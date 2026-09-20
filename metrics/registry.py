"""进程内指标注册表：counter/gauge 按名字注册，带标签维度，支持快照导出。"""
import threading

__all__ = ["Registry", "Counter", "Gauge", "DuplicateMetric"]


class DuplicateMetric(KeyError):
    """同名指标重复注册。"""


def _key(labels, label_names):
    # 按注册时声明的标签名顺序取值，未提供的维度记为空串
    return tuple(str(labels.get(name, "")) for name in label_names)


class _Metric:
    kind = "metric"

    def __init__(self, name, label_names):
        self.name = name
        self.label_names = tuple(label_names)
        self._lock = threading.Lock()
        self._series = {}

    def _bump(self, key, amount):
        raise NotImplementedError

    def snapshot(self):
        with self._lock:
            items = sorted(self._series.items())
        return {
            "name": self.name,
            "type": self.kind,
            "label_names": list(self.label_names),
            "series": [
                {"labels": dict(zip(self.label_names, key)), "value": value}
                for key, value in items
            ],
        }


class Counter(_Metric):
    """单调递增计数器，每个标签组合是一条独立序列。"""

    kind = "counter"

    def inc(self, amount=1, **labels):
        key = _key(labels, self.label_names)
        with self._lock:
            self._series[key] = self._series.get(key, 0) + amount

    def value(self, **labels):
        return self._series.get(_key(labels, self.label_names), 0)


class Gauge(_Metric):
    """可增可减的瞬时值，每个标签组合是一条独立序列。"""

    kind = "gauge"

    def set(self, value, **labels):
        key = _key(labels, self.label_names)
        with self._lock:
            self._series[key] = value

    def value(self, **labels):
        return self._series.get(_key(labels, self.label_names))


class Registry:
    """指标注册表，全局按名字唯一。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._metrics = {}

    def _register(self, metric):
        with self._lock:
            if metric.name in self._metrics:
                raise DuplicateMetric(metric.name)
            self._metrics[metric.name] = metric
        return metric

    def counter(self, name, label_names=()):
        return self._register(Counter(name, label_names))

    def gauge(self, name, label_names=()):
        return self._register(Gauge(name, label_names))

    def get(self, name):
        return self._metrics[name]

    def snapshot(self):
        with self._lock:
            metrics = sorted(self._metrics.values(), key=lambda m: m.name)
        return {"metrics": [metric.snapshot() for metric in metrics]}
