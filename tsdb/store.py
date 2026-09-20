"""内存时序库：写入 (timestamp, value) 点，按区间查询原始点。"""
import bisect


class TimeSeriesStore:
    """把原始点按时间戳升序放在两个平行列表里，支持闭区间查询。"""

    def __init__(self):
        self._ts = []    # 时间戳，升序
        self._vals = []  # 与时间戳一一对应的值

    def write(self, ts, value):
        """写入单个点，时间戳可以乱序到达。"""
        i = bisect.bisect_right(self._ts, ts)
        self._ts.insert(i, ts)
        self._vals.insert(i, value)

    def write_many(self, points):
        """批量写入可迭代的 (ts, value) 序列。"""
        for ts, value in points:
            self.write(ts, value)

    def query(self, start, end):
        """返回 [start, end] 闭区间内的原始点，按时间升序。"""
        lo = bisect.bisect_left(self._ts, start)
        hi = bisect.bisect_right(self._ts, end)
        return list(zip(self._ts[lo:hi], self._vals[lo:hi]))

    def span(self):
        """返回 (最早时间戳, 最晚时间戳)，空库返回 None。"""
        if not self._ts:
            return None
        return self._ts[0], self._ts[-1]

    def __len__(self):
        """当前保存的原始点总数。"""
        return len(self._ts)
