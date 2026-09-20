"""降采样归档：原始点按对齐窗口聚合成精度层，查询按范围自动选层。"""
from .store import TimeSeriesStore


class _Bucket:
    """可增量合并的窗口聚合态，迟到点与重复归档都靠它保证正确。"""

    __slots__ = ("total", "count", "min", "max")

    def __init__(self):
        self.total = 0.0
        self.count = 0
        self.min = None
        self.max = None

    def add(self, value):
        self.total += value
        self.count += 1
        self.min = value if self.min is None else min(self.min, value)
        self.max = value if self.max is None else max(self.max, value)

    @property
    def avg(self):
        return self.total / self.count


class RollupStore:
    """原始点加若干降采样精度层；归档后原始点即被丢弃，内存里只留聚合态。"""

    def __init__(self, resolutions=(60, 3600), min_buckets=2):
        if not resolutions:
            raise ValueError("至少需要一个归档精度层")
        self._resolutions = sorted(resolutions)
        self._min_buckets = min_buckets
        self._raw = TimeSeriesStore()
        self._layers = {r: {} for r in self._resolutions}
        self._archived_until = None

    def write(self, ts, value):
        """写入单个点；早于归档水位线的迟到点直接并入各层聚合态。"""
        if self._archived_until is not None and ts < self._archived_until:
            self._merge(ts, value)
        else:
            self._raw.write(ts, value)

    def write_many(self, points):
        """批量写入可迭代的 (ts, value) 序列。"""
        for ts, value in points:
            self.write(ts, value)

    def _merge(self, ts, value):
        for r in self._resolutions:
            window = (ts // r) * r
            bucket = self._layers[r].setdefault(window, _Bucket())
            bucket.add(value)

    def archive(self, cutoff):
        """把 ts < cutoff 的原始点并入各精度层并丢弃；重复调用结果不变。"""
        for ts, value in self._raw.pop_before(cutoff):
            self._merge(ts, value)
        if self._archived_until is None or cutoff > self._archived_until:
            self._archived_until = cutoff

    def query(self, start, end):
        """按范围选层：大范围返回归档桶的 (窗口起点, 均值)，小范围返回原始点。"""
        r = self._pick_resolution(end - start)
        if r is None:
            return self._raw.query(start, end)
        points = [
            (w, bucket.avg)
            for w, bucket in self._layers[r].items()
            if start <= w and w + r - 1 <= end
        ]
        points.extend(self._raw.query(start, end))
        points.sort()
        return points

    def _pick_resolution(self, span):
        chosen = None
        for r in self._resolutions:
            if span // r >= self._min_buckets:
                chosen = r
        return chosen

    def __len__(self):
        """当前仍常驻内存的原始点总数。"""
        return len(self._raw)
