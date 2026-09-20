"""事件时间滑动窗口。

SlidingWindow: 最近 N 秒的计数窗口，按事件时间推进，窗口外数据真实淘汰，
淘汰出的子窗口聚合成 WindowResult 产出，支持相邻产出合并。
WindowSet: 同一份事件流并行维护多个不同长度的窗口，各自独立淘汰。
时钟从外部注入，纯标准库。
"""

import math
import threading
import time
from collections import namedtuple

# 一个已关闭子窗口的聚合产出，覆盖闭开区间 [start, end)。
WindowResult = namedtuple("WindowResult", ["start", "end", "total"])


class SlidingWindow:
    """最近 size 秒的滑动窗口，按 bucket 粒度分桶、按事件时间推进。

    size: 窗口长度（秒）；bucket: 子窗口（桶）长度（秒），size 必须是
    bucket 的整数倍。clock: 注入时钟，只记录到达时刻，窗口推进只看事件
    时间（水位线 = 见过的最大事件时间），重放历史数据可复现。
    on_late: 迟到事件（ts 早于窗口左缘）的处理策略，"drop" 丢弃 /
    "keep" 留档；两种都计入 late_count()/late_total()，不默默吞。
    closed_retention: closed() 产出最多保留的条数，超出的从头部过期；
    None 表示不限。
    """

    def __init__(self, size, bucket, clock=time.monotonic, on_late="drop",
                 closed_retention=None):
        if size <= 0 or bucket <= 0:
            raise ValueError("size 和 bucket 必须为正")
        ratio = size / bucket
        if abs(ratio - round(ratio)) > 1e-9:
            raise ValueError("size 必须是 bucket 的整数倍")
        if on_late not in ("drop", "keep"):
            raise ValueError('on_late 只能是 "drop" 或 "keep"')
        self.size = float(size)
        self.bucket = float(bucket)
        self._clock = clock
        self._on_late = on_late
        self._retention = closed_retention
        self._lock = threading.Lock()
        # 桶序号 -> [事件列表, 界内合计, 已剪除的界外合计]
        self._buckets = {}
        self._wm = None            # 水位线 = 见过的最大事件时间
        self._closed = []          # 被淘汰子窗口的聚合产出
        self._late_count = 0
        self._late_total = 0.0
        self._late_events = []     # on_late="keep" 时留档
        self._last_arrival = None

    def add(self, ts, v=1):
        """记一个事件，返回 True 入账 / False 迟到（按 on_late 策略处理）。

        事件时间不保证递增：落在窗口内的乱序事件正常入账；ts 早于窗口
        左缘的判为迟到，绝不默默吞掉。
        """
        with self._lock:
            self._last_arrival = self._clock()
            if self._wm is None or ts > self._wm:
                self._wm = ts
            if ts < self._left():
                self._late_count += 1
                self._late_total += v
                if self._on_late == "keep":
                    self._late_events.append((ts, v))
                return False
            idx = math.floor(ts / self.bucket + 1e-9)
            entry = self._buckets.get(idx)
            if entry is None:
                entry = self._buckets[idx] = [[], 0.0, 0.0]
            entry[0].append((ts, v))
            entry[1] += v
            self._evict()
            return True

    def sum(self):
        """当前窗口 [左缘, 水位线] 内的计数和。"""
        with self._lock:
            return sum(entry[1] for entry in self._buckets.values())

    def count(self):
        """当前窗口内保留的事件条数。"""
        with self._lock:
            return sum(len(entry[0]) for entry in self._buckets.values())

    def watermark(self):
        """当前水位线（最大事件时间），没有事件时返回 None。"""
        with self._lock:
            return self._wm

    def left(self):
        """当前窗口左缘（水位线 - size，含），没有事件时返回 None。"""
        with self._lock:
            if self._wm is None:
                return None
            return self._left()

    def closed(self):
        """已被淘汰子窗口的聚合产出列表（WindowResult），按时间升序。"""
        with self._lock:
            return list(self._closed)

    def merge_closed(self):
        """把 closed() 中时间连续的相邻产出合并成大窗口结果，返回新列表。

        仅当 a.end == b.start（闭开区间首尾相接）且两条都未过期（仍在
        closed_retention 保留范围内）时才合并；closed() 本身不变。
        """
        with self._lock:
            results = list(self._closed)
        merged = []
        for r in results:
            if merged and merged[-1].end == r.start:
                prev = merged[-1]
                merged[-1] = WindowResult(prev.start, r.end,
                                          prev.total + r.total)
            else:
                merged.append(r)
        return merged

    def late_count(self):
        """被判迟到的事件条数。"""
        with self._lock:
            return self._late_count

    def late_total(self):
        """被判迟到事件的计数增量合计。"""
        with self._lock:
            return self._late_total

    def late(self):
        """on_late="keep" 时留档的迟到事件 (ts, v) 列表。"""
        with self._lock:
            return list(self._late_events)

    def last_arrival(self):
        """最近一次 add 的到达时刻（注入时钟读数），没有事件时返回 None。"""
        with self._lock:
            return self._last_arrival

    def reset(self):
        """清空全部事件、桶、产出与统计。"""
        with self._lock:
            self._buckets.clear()
            self._wm = None
            self._closed.clear()
            self._late_count = 0
            self._late_total = 0.0
            self._late_events.clear()
            self._last_arrival = None

    def _left(self):
        return self._wm - self.size

    def _evict(self):
        left = self._left()
        for idx in sorted(self._buckets):
            start = idx * self.bucket
            end = start + self.bucket
            events, live, pruned = self._buckets[idx]
            if end <= left:
                # 整桶滑出窗口：聚合成一条产出后真实删除
                del self._buckets[idx]
                self._emit(start, end, live + pruned)
            elif start < left:
                # 跨左缘的桶：先剪掉界外事件，计入 pruned 留给产出
                kept = [(ts, v) for ts, v in events if ts >= left]
                cut = sum(v for ts, v in events if ts < left)
                if cut:
                    self._buckets[idx] = [kept, live - cut, pruned + cut]

    def _emit(self, start, end, total):
        self._closed.append(WindowResult(start, end, total))
        if self._retention is not None:
            excess = len(self._closed) - self._retention
            if excess > 0:
                del self._closed[:excess]


class WindowSet:
    """同一份事件流并行维护多个不同长度的滑动窗口。

    每个窗口各自维护水位线与桶，各自独立淘汰，短的到点就走。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._windows = []

    def add_window(self, size, bucket, on_late="drop", closed_retention=None):
        """挂一个窗口，返回创建的 SlidingWindow。"""
        w = SlidingWindow(size, bucket, clock=self._clock, on_late=on_late,
                          closed_retention=closed_retention)
        self._windows.append(w)
        return w

    def add(self, ts, v=1):
        """把事件分发给全部窗口，返回各窗口的入账结果列表。"""
        return [w.add(ts, v) for w in self._windows]

    def sums(self):
        """各窗口当前的计数和列表，顺序与 add_window 一致。"""
        return [w.sum() for w in self._windows]
