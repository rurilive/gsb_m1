"""内存时序库：写入 (timestamp, value) 点，按区间查询；旧数据可降采样归档。"""
import bisect


class TimeSeriesStore:
    """原始点 + 降采样归档层。

    原始点按时间戳升序放在两个平行列表里；归档层按对齐窗口保存
    (count, total, min, max) 聚合，窗口右端不超过 archive(before) 的
    原始点在归档后从原始层删除。
    """

    def __init__(self, window=60):
        self._ts = []    # 时间戳，升序
        self._vals = []  # 与时间戳一一对应的值
        self._window = window
        self._rollup = {}         # 窗口起点 -> [count, total, min, max]
        self._rollup_starts = []  # 窗口起点，升序

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

    def archive(self, before=None):
        """把窗口右端 <= before 的原始点并入归档层，并从原始层删除。

        before 为 None 时归档当前所有点。窗口按绝对边界对齐
        （起点 = ts - ts % window），与首点到达时间无关。
        已归档的点即从原始层移除，重复调用不会重复计数；
        迟到的点仍在原始层，下次调用时并入同一窗口的聚合。
        """
        w = self._window
        keep_ts, keep_vals = [], []
        for ts, val in zip(self._ts, self._vals):
            wstart = ts - (ts % w)
            if before is None or wstart + w <= before:
                self._merge_rollup(wstart, val)
            else:
                keep_ts.append(ts)
                keep_vals.append(val)
        self._ts, self._vals = keep_ts, keep_vals

    def _merge_rollup(self, wstart, val):
        agg = self._rollup.get(wstart)
        if agg is None:
            self._rollup[wstart] = [1, val, val, val]
            bisect.insort(self._rollup_starts, wstart)
        else:
            agg[0] += 1
            agg[1] += val
            agg[2] = min(agg[2], val)
            agg[3] = max(agg[3], val)

    def query_rollup(self, start, end):
        """返回与 [start, end] 相交的归档窗口，按窗口起点升序。

        每行是 (窗口起点, count, total, min, max)，平均值 = total / count。
        """
        w = self._window
        lo = bisect.bisect_left(self._rollup_starts, start - (start % w))
        out = []
        for wstart in self._rollup_starts[lo:]:
            if wstart > end:
                break
            count, total, lo_v, hi_v = self._rollup[wstart]
            out.append((wstart, count, total, lo_v, hi_v))
        return out

    def query_auto(self, start, end):
        """按范围自动选层：跨度 >= 2 个窗口走归档层（窗口均值），否则走原始点。

        返回统一的 (ts, value) 序列，归档层用窗口起点配窗口均值。
        """
        if end - start >= 2 * self._window:
            return [(ws, total / count)
                    for ws, count, total, _, _ in self.query_rollup(start, end)]
        return self.query(start, end)

    def span(self):
        """返回 (最早时间戳, 最晚时间戳)，空库返回 None。"""
        if not self._ts:
            return None
        return self._ts[0], self._ts[-1]

    def __len__(self):
        """当前保存的原始点总数。"""
        return len(self._ts)
