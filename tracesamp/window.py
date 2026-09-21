"""滑动窗口计数器：按固定时长分桶，统计最近一段时间的 span 条数。

时间一律从注入的 clock 读取（默认 time.monotonic）。桶按 clock 的绝对值切分，
同一个刻度落在同一个桶里，所以假时钟能把窗口的滚动点卡得很准。
多个计数器（total、sampled）共用同一份窗口，键名由调用方自己定。
"""

import threading
import time


class SlidingWindow:
    """最近 window_seconds 秒内的计数，按 buckets 个桶分摊。

    window_seconds: 窗口长度，读到的计数覆盖的时间范围。
    buckets: 窗口切成几格，越小滚动越粗。
    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic。
    """

    def __init__(self, window_seconds=1.0, buckets=4, clock=time.monotonic):
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if buckets < 1:
            raise ValueError("buckets must be >= 1")
        self._window_seconds = float(window_seconds)
        self._bucket_count = int(buckets)
        self._bucket_seconds = self._window_seconds / self._bucket_count
        self._clock = clock
        self._lock = threading.Lock()
        # 每个槽位记自己装的是哪个绝对桶格（-1 表示空）。换格时只清真正
        # 滑出窗口的旧槽，不再一格滚、整窗清空。
        self._slots = [dict() for _ in range(self._bucket_count)]
        self._slot_indexes = [-1] * self._bucket_count
        self._current = int(clock() / self._bucket_seconds)

    @property
    def window_seconds(self):
        return self._window_seconds

    def add(self, key, n=1):
        """给 key 记 n 条，记在当前桶里。"""
        now = self._clock()
        with self._lock:
            index = self._rotate(now)
            self._add(index, key, n)

    def add2(self, key1, delta1, key2=None, delta2=0, now=None):
        """热路径专用：至多两个计数原子记一笔，调用方自带键名，无额外分配。"""
        if now is None:
            now = self._clock()
        with self._lock:
            index = self._rotate(now)
            if delta1:
                self._add(index, key1, delta1)
            if key2 is not None and delta2:
                self._add(index, key2, delta2)

    def count(self, key):
        """窗口内 key 的合计条数。"""
        now = self._clock()
        with self._lock:
            self._rotate(now)
            return self._sum(key)

    def snapshot(self, keys):
        """原子读多个 key 的窗口合计与窗口实际覆盖时长。

        返回 (各 key 的计数元组, coverage_seconds)。所有键在同一份桶状态下
        读出，中间不会插进滚动；控制器拿它就不会把两个计数读岔。
        冷启动或长时空闲后窗口没装满，coverage 只算真正有桶覆盖的时长，
        每秒均值按实际覆盖时长归一，而不是按完整窗口稀释。
        """
        now = self._clock()
        with self._lock:
            index = self._rotate(now)
            counts = tuple(self._sum(key) for key in keys)
            oldest = self._oldest_valid()
            if oldest is None:
                coverage = 0.0
            else:
                covered_buckets = index - oldest + 1
                coverage = covered_buckets * self._bucket_seconds
            return counts, min(coverage, self._window_seconds)

    def per_second(self, key):
        """窗口内 key 的每秒均值。"""
        return self.count(key) / self._window_seconds

    def reset(self):
        """清空所有桶。"""
        with self._lock:
            for bucket in self._slots:
                bucket.clear()
            self._slot_indexes = [-1] * self._bucket_count

    # ---- 内部实现 ----

    def _rotate(self, now):
        """推进到 now 所在桶格，返回当前格编号。

        槽位不在这里 eager 清空：每个槽带着自己的桶格编号，写入时槽位被
        新桶格复用才清，读数时按桶格编号过滤。这样写入是 O(1)，长时间空闲
        后再写也不会把早已滑出窗口的旧数据"复活"进合计。
        """
        index = int(now / self._bucket_seconds)
        self._current = index
        return index

    def _add(self, index, key, n):
        slot = index % self._bucket_count
        if self._slot_indexes[slot] != index:
            # 槽位属于更早的桶格（正常滚动或时钟跳变），整槽作废后再写。
            self._slots[slot].clear()
            self._slot_indexes[slot] = index
        bucket = self._slots[slot]
        bucket[key] = bucket.get(key, 0) + n

    def _sum(self, key):
        oldest_kept = self._current - self._bucket_count + 1
        total = 0
        for slot, slot_index in zip(self._slots, self._slot_indexes):
            if slot_index >= 0 and slot_index >= oldest_kept:
                total += slot.get(key, 0)
        return total

    def _oldest_valid(self):
        oldest_kept = self._current - self._bucket_count + 1
        oldest = None
        for slot_index in self._slot_indexes:
            if slot_index >= 0 and slot_index >= oldest_kept and (
                    oldest is None or slot_index < oldest):
                oldest = slot_index
        return oldest
