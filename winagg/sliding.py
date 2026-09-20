"""滑动窗口聚合。

窗口按事件时间推进：watermark 为已见最大事件时间，与到达时刻无关，
重放同一份历史数据得到同样的窗口轨迹。滑动窗口覆盖
[watermark - size, watermark]，左边界以远的事件在 watermark 推进时
被真正淘汰（从缓冲删除，不是查询时过滤）。

乱序到达：ts >= watermark - size 的迟到事件仍计入窗口；ts 更早的按
late_policy 处理，"drop" 丢弃并记 dropped，"count" 单独记迟到数。

滚动窗口（长度 size，闭开 [start, end)）在 end <= watermark 时关闭，
聚合结果作为 ClosedWindow 产出，drain_emissions() 可捞走离线补数。
已关闭窗口的产出不再修改；关闭后才到的同段事件只进滑动窗口和。
"""

import threading
import time
from collections import namedtuple


ClosedWindow = namedtuple("ClosedWindow", ["start", "end", "total", "count"])


class SlidingWindow:
    """最近 N 秒（事件时间）的计数和，窗口外数据真淘汰。

    size: 窗口长度（秒）。
    clock: 注入时钟，只用于记到达时刻，不驱动窗口。
    late_policy: 出界迟到事件的处理策略，"drop" 或 "count"。
    emission_retention: 已关闭窗口产出的保留时长（按事件时间），
        超过 watermark - end > retention 的产出被清除，merge 拒绝；
        None 表示不过期。
    """

    def __init__(self, size, clock=time.monotonic, late_policy="drop",
                 emission_retention=None):
        if size <= 0:
            raise ValueError("size must be positive")
        if late_policy not in ("drop", "count"):
            raise ValueError("late_policy must be 'drop' or 'count'")
        self._size = float(size)
        self._clock = clock
        self._late_policy = late_policy
        self._retention = (None if emission_retention is None
                           else float(emission_retention))
        self._lock = threading.Lock()
        self._events = []        # 窗口内 (ts, v)，乱序追加，推进时淘汰
        self._sum = 0.0
        self._watermark = None
        self._buckets = {}       # 未关闭滚动窗口: index -> [total, count]
        self._emissions = []     # 已关闭窗口产出
        self._dropped = 0
        self._late_count = 0
        self._late_total = 0.0
        self._last_arrival = None

    def add(self, ts, v=1):
        """记一个事件，返回当前窗口和。出界迟到事件按策略处理，不进窗口。"""
        with self._lock:
            self._last_arrival = self._clock()
            if self._watermark is None or ts > self._watermark:
                self._watermark = ts
                self._advance()
            if ts < self._watermark - self._size:
                if self._late_policy == "drop":
                    self._dropped += 1
                else:
                    self._late_count += 1
                    self._late_total += v
                return self._sum
            self._events.append((ts, v))
            self._sum += v
            index = int(ts // self._size)
            if (index + 1) * self._size > self._watermark:
                # 只进未关闭的滚动窗口；已关闭的产出不再改
                bucket = self._buckets.setdefault(index, [0.0, 0])
                bucket[0] += v
                bucket[1] += 1
            return self._sum

    def _advance(self):
        """watermark 更新后：淘汰窗口外事件、关闭到点的滚动窗口、清过期产出。"""
        left = self._watermark - self._size
        kept = []
        for ts, v in self._events:
            if ts < left:
                self._sum -= v
            else:
                kept.append((ts, v))
        self._events = kept
        for index in sorted(self._buckets):
            end = (index + 1) * self._size
            if end <= self._watermark:
                total, count = self._buckets.pop(index)
                self._emissions.append(
                    ClosedWindow(index * self._size, end, total, count))
        self._emissions = [w for w in self._emissions if not self._expired(w)]

    def _expired(self, window):
        if self._retention is None or self._watermark is None:
            return False
        return self._watermark - window.end > self._retention

    def sum(self):
        """当前窗口 [watermark - size, watermark] 内的计数和。"""
        with self._lock:
            return self._sum

    def buffered(self):
        """窗口内暂存的事件条数（淘汰后真实剩余）。"""
        with self._lock:
            return len(self._events)

    def watermark(self):
        """已见最大事件时间，没有事件时返回 None。"""
        with self._lock:
            return self._watermark

    def dropped(self):
        """被丢弃的出界迟到事件条数（late_policy="drop"）。"""
        with self._lock:
            return self._dropped

    def late(self):
        """记下的迟到事件 (条数, 计数和)（late_policy="count"）。"""
        with self._lock:
            return (self._late_count, self._late_total)

    def last_arrival(self):
        """最近一次 add 的到达时刻，没有事件时返回 None。"""
        with self._lock:
            return self._last_arrival

    def emissions(self):
        """当前保留的已关闭窗口产出，按时间升序。"""
        with self._lock:
            return tuple(self._emissions)

    def drain_emissions(self):
        """取出并清空已关闭窗口产出，供离线补数捞走。"""
        with self._lock:
            out = self._emissions
            self._emissions = []
            return out

    def merge(self, a, b):
        """合并两个相邻已关闭窗口为大窗口结果。

        只允许 a.end == b.start 时间连续且两个窗口都未过期，否则 ValueError。
        """
        with self._lock:
            if a.end != b.start:
                raise ValueError("windows are not adjacent")
            if self._expired(a) or self._expired(b):
                raise ValueError("window expired")
            return ClosedWindow(a.start, b.end, a.total + b.total,
                                a.count + b.count)


class MultiWindow:
    """同一份数据并行维护多个不同长度的滑动窗口，各自独立淘汰。"""

    def __init__(self, sizes, clock=time.monotonic, late_policy="drop",
                 emission_retention=None):
        sizes = [float(s) for s in sizes]
        if not sizes:
            raise ValueError("sizes must not be empty")
        self._windows = {
            s: SlidingWindow(s, clock=clock, late_policy=late_policy,
                             emission_retention=emission_retention)
            for s in sizes
        }

    def add(self, ts, v=1):
        """把事件喂给全部窗口。"""
        for w in self._windows.values():
            w.add(ts, v)

    def sum(self, size):
        """指定长度窗口的当前计数和。"""
        return self._windows[float(size)].sum()

    def window(self, size):
        """取指定长度的底层 SlidingWindow。"""
        return self._windows[float(size)]

    def sizes(self):
        """并行维护的窗口长度。"""
        return tuple(self._windows)
