"""对象状态快照的暂存与按时刻读取。

每个对象维持一串带时间戳的快照，内部按时间升序保存；读取时
取「不晚于给定时刻」的最近一张。纯标准库。
"""

import bisect
import threading
import time


class RetentionPolicy:
    """快照保留策略。

    三档判断，边界均为闭区间（age 恰好等于阈值算进更近的一档）：

    - 最近 recent_seconds 内：全部保留
    - 再往前到 hourly_seconds：每个时钟小时只留该小时最后一张
    - 更早：每个自然天只留当天最后一张，长期保留不再向下删除

    max_snapshots 为每个对象的条数兜底：三档筛完仍超出时，从最旧的
    非按住快照继续丢；被按住（pin）的快照不计入上限，永不参与删除。
    小时/天桶以 UTC 整点、零点对齐（对注入的假时钟同样成立）。
    """

    HOUR_SECONDS = 3600
    DAY_SECONDS = 86400

    def __init__(self, recent_seconds, hourly_seconds, max_snapshots):
        if recent_seconds < 0:
            raise ValueError("recent_seconds 不能为负")
        if hourly_seconds is not None and hourly_seconds < recent_seconds:
            raise ValueError("hourly_seconds 不能小于 recent_seconds")
        if max_snapshots is not None and max_snapshots < 1:
            raise ValueError("max_snapshots 至少为 1")
        self.recent_seconds = recent_seconds
        self.hourly_seconds = hourly_seconds
        self.max_snapshots = max_snapshots


class SnapshotStore:
    """按对象保存快照序列。

    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic，
    测试可注入假时钟来精确控制时间轴。
    retention: RetentionPolicy，缺省（None）时不做任何回收。
    gc_interval: 写入时节流的最小回收间隔（秒）。同一对象两次自动回收
    至少间隔这么久，避免高频 take 反复重扫；置 0 表示每次 take 都回收。
    """

    def __init__(self, clock=time.monotonic, retention=None, gc_interval=60.0):
        self._clock = clock
        self._retention = retention
        self._gc_interval = gc_interval
        self._lock = threading.Lock()
        # obj -> [[ts, state], ...]，ts 升序
        self._snaps = {}
        # obj -> set(被按住的时间戳)，回收时一律绕开
        self._pins = {}
        # obj -> 该对象最近一次自动回收时刻
        self._last_gc = {}
        self._gc_runs = 0
        self._total_released = 0
        self._last_released = 0
        self._last_run_at = None

    def pin(self, obj, ts):
        """按住 obj 在 ts 时刻的那张快照，使其永不被回收。

        时间戳必须精确匹配该对象某张现存快照，否则抛 KeyError。
        """
        with self._lock:
            snaps = self._snaps.get(obj)
            if not snaps or not any(s[0] == ts for s in snaps):
                raise KeyError((obj, ts))
            self._pins.setdefault(obj, set()).add(ts)

    def unpin(self, obj, ts):
        """解除按住；该时间戳未被按住时静默无事。"""
        with self._lock:
            pins = self._pins.get(obj)
            if pins:
                pins.discard(ts)

    def pins(self, obj):
        """返回 obj 当前被按住的快照时间戳，升序。"""
        with self._lock:
            return sorted(self._pins.get(obj, ()))

    def take(self, obj, state):
        """给 obj 存一张当前时刻的快照，返回该快照的时间戳。"""
        with self._lock:
            ts = self._clock()
            self._snaps.setdefault(obj, []).append([ts, state])
            if self._retention is not None:
                last = self._last_gc.get(obj)
                if last is None or ts - last >= self._gc_interval:
                    self._gc_locked(obj, ts)
            return ts

    def gc(self, obj=None):
        """立即执行一轮回收，返回本轮释放条数。

        obj 缺省时回收全部对象（手动全量）；指定时只回收该对象。
        不受 gc_interval 节流限制，也不影响 take 的节流计时。
        """
        with self._lock:
            now = self._clock()
            if self._retention is None:
                return 0
            if obj is None:
                released = 0
                for key in list(self._snaps):
                    released += self._gc_locked(key, now)
                return released
            return self._gc_locked(obj, now)

    def gc_stats(self):
        """回收可观测信息：轮数、上轮释放、累计释放、最近回收时刻。"""
        with self._lock:
            return {
                "gc_runs": self._gc_runs,
                "last_released": self._last_released,
                "total_released": self._total_released,
                "last_run_at": self._last_run_at,
            }

    def _gc_locked(self, obj, now):
        """对单个对象跑一轮回收。调用方持锁。"""
        policy = self._retention
        snaps = self._snaps.get(obj)
        if not snaps:
            return 0
        pins = self._pins.get(obj, ())

        recent_cut = now - policy.recent_seconds
        hourly_cut = (
            None
            if policy.hourly_seconds is None
            else now - policy.hourly_seconds
        )

        # 每个小时/天桶里最后一张快照的时间戳。桶以整除对齐，
        # 全部快照都参与登记，桶内只要还有更近的一张，旧候选就该被抽掉。
        last_in_hour = {}
        last_in_day = {}
        for ts, _state in snaps:
            last_in_hour[int(ts // RetentionPolicy.HOUR_SECONDS)] = ts
            last_in_day[int(ts // RetentionPolicy.DAY_SECONDS)] = ts

        survivors = []
        for ts, state in snaps:
            keep = ts in pins
            if not keep:
                if ts >= recent_cut:
                    keep = True
                elif hourly_cut is not None and ts >= hourly_cut:
                    keep = (
                        last_in_hour[
                            int(ts // RetentionPolicy.HOUR_SECONDS)
                        ]
                        == ts
                    )
                else:
                    keep = (
                        last_in_day[
                            int(ts // RetentionPolicy.DAY_SECONDS)
                        ]
                        == ts
                    )
            if keep:
                survivors.append([ts, state])

        # 条数兜底：只从最旧的非按住快照继续丢。
        if policy.max_snapshots is not None:
            unpinned_count = sum(1 for s in survivors if s[0] not in pins)
            excess = unpinned_count - policy.max_snapshots
            if excess > 0:
                trimmed = []
                for snap in survivors:
                    if excess > 0 and snap[0] not in pins:
                        excess -= 1
                        continue
                    trimmed.append(snap)
                survivors = trimmed

        released = len(snaps) - len(survivors)
        self._snaps[obj] = survivors
        self._last_gc[obj] = now
        self._gc_runs += 1
        self._last_released = released
        self._total_released += released
        self._last_run_at = now
        return released

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
