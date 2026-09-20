"""对象状态快照的暂存与按时刻读取。

每个对象维持一串带时间戳的快照，内部按时间升序保存；读取时
取「不晚于给定时刻」的最近一张。纯标准库。
"""

import bisect
import threading
import time


_HOUR = 3600.0
_DAY = 86400.0


class RetentionPolicy:
    """快照保留策略。

    以「距当前时刻的 age」分三档，边界归入较新的一档：
    - age <= recent_window：一条不动；
    - recent_window < age <= hourly_window：每小时只留该小时最后一张；
    - age > hourly_window：每天留当天最后一张。
    max_per_obj 为每对象条数上限兜底：上面筛完还超，就从最旧的
    非 pin 快照继续丢（pin 住的永远不丢）。
    """

    def __init__(self, recent_window, hourly_window, max_per_obj=None):
        if recent_window <= 0:
            raise ValueError("recent_window 必须为正")
        if hourly_window < recent_window:
            raise ValueError("hourly_window 不能小于 recent_window")
        if max_per_obj is not None and max_per_obj <= 0:
            raise ValueError("max_per_obj 必须为正")
        self.recent_window = float(recent_window)
        self.hourly_window = float(hourly_window)
        self.max_per_obj = max_per_obj


class SnapshotStore:
    """按对象保存快照序列。

    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic，
    测试可注入假时钟来精确控制时间轴。
    retention: 可选的 RetentionPolicy；给了就在写入时自动回收。
    gc_interval: 两次回收的最小时钟间隔（秒），避免每次 take 都全表重扫。
    """

    def __init__(self, clock=time.monotonic, retention=None, gc_interval=300.0):
        self._clock = clock
        self._lock = threading.Lock()
        # obj -> [[ts, state], ...]，ts 升序
        self._snaps = {}
        self._retention = retention
        self._gc_interval = float(gc_interval)
        self._last_gc = None
        # obj -> {ts, ...}，被按住的快照时刻，回收时绕开
        self._pins = {}
        self._gc_runs = 0
        self._gc_last_run = None
        self._gc_last_released = 0
        self._gc_total_released = 0

    def take(self, obj, state):
        """给 obj 存一张当前时刻的快照，返回该快照的时间戳。"""
        with self._lock:
            ts = self._clock()
            self._snaps.setdefault(obj, []).append([ts, state])
            self._maybe_gc(ts)
            return ts

    def get(self, obj, ts):
        """取 obj 在 ts 时刻的状态：不晚于 ts 的最近一张快照。

        该对象没有任何不晚于 ts 的快照时返回 None。
        """
        with self._lock:
            snaps = self._snaps.get(obj)
            if not snaps:
                return None
            times = [s[0] for s in snaps]
            i = bisect.bisect_right(times, ts) - 1
            if i < 0:
                return None
            return snaps[i][1]

    def list(self, obj):
        """返回 obj 全部快照的时间戳，升序；没有快照时返回空列表。"""
        with self._lock:
            snaps = self._snaps.get(obj)
            if not snaps:
                return []
            return [s[0] for s in snaps]

    def pin(self, obj, ts):
        """按住 obj 在 ts 时刻的快照，回收时绕开它。"""
        with self._lock:
            self._pins.setdefault(obj, set()).add(ts)

    def unpin(self, obj, ts):
        """松开之前按住的快照，之后回收不再特殊照顾它。"""
        with self._lock:
            pins = self._pins.get(obj)
            if pins:
                pins.discard(ts)

    def gc_stats(self):
        """回收统计：轮数、最近一次回收时刻、最近一轮与累计释放条数。"""
        with self._lock:
            return {
                "runs": self._gc_runs,
                "last_run": self._gc_last_run,
                "last_released": self._gc_last_released,
                "total_released": self._gc_total_released,
            }

    def collect_now(self):
        """立即跑一轮回收（跳过节流），返回本轮释放的条数。"""
        if self._retention is None:
            return 0
        with self._lock:
            return self._gc(self._clock())

    def _maybe_gc(self, ts):
        if self._retention is None:
            return
        if self._last_gc is None or ts - self._last_gc >= self._gc_interval:
            self._gc(ts)

    def _gc(self, now):
        pol = self._retention
        released = 0
        for obj, snaps in self._snaps.items():
            pinned = self._pins.get(obj) or ()
            keep = self._select_keeps(snaps, pinned, now, pol)
            released += len(snaps) - len(keep)
            if len(keep) != len(snaps):
                snaps[:] = keep
        self._gc_runs += 1
        self._gc_last_run = now
        self._gc_last_released = released
        self._gc_total_released += released
        self._last_gc = now
        return released

    @staticmethod
    def _select_keeps(snaps, pinned, now, pol):
        recent_cut = now - pol.recent_window
        hourly_cut = now - pol.hourly_window
        # 抽稀区里每个小时/天桶要留的最后一张的下标；ts 升序遍历，
        # 同桶后者覆盖前者，留下的即桶内最后一张。桶键带档位前缀，
        # 避免小时桶号与天桶号相撞。
        bucket_last = {}
        for i, (ts, _state) in enumerate(snaps):
            if ts >= recent_cut:
                break
            if ts >= hourly_cut:
                bucket = ("h", ts // _HOUR)
            else:
                bucket = ("d", ts // _DAY)
            bucket_last[bucket] = i
        keep_idx = set(bucket_last.values())
        keep = [
            s for i, s in enumerate(snaps)
            if s[0] >= recent_cut or i in keep_idx or s[0] in pinned
        ]
        if pol.max_per_obj is not None and len(keep) > pol.max_per_obj:
            excess = len(keep) - pol.max_per_obj
            trimmed = []
            for s in keep:  # keep 升序，从最旧的非 pin 开始丢
                if excess and s[0] not in pinned:
                    excess -= 1
                    continue
                trimmed.append(s)
            keep = trimmed
        return keep
