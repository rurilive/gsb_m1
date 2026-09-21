"""滑动窗口计数器：按固定时长分桶，统计最近一段时间的 span 条数。

时间一律从注入的 clock 读取（默认 time.monotonic）。桶按 clock 的绝对值切分，
同一个刻度落在同一个桶里，所以假时钟能把窗口的滚动点卡得很准。
多个计数器（total、sampled）共用同一份窗口，键名由调用方自己定。

桶只在它对应的时间段彻底滑出窗口时才被清空复用，因此跨桶边界时计数不会
整条归零，count 始终是最近 window_seconds 秒的连续视图。add_many 一次给
多个键记账、snapshot 一次读出多个键，保证不同计数器（total、sampled）
落在同一批桶上，不会互相读岔。
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
        self._buckets = [dict() for _ in range(self._bucket_count)]
        self._current = int(clock() / self._bucket_seconds)

    @property
    def window_seconds(self):
        return self._window_seconds

    def add(self, key, n=1):
        """给 key 记 n 条，记在当前桶里。"""
        self.add_many(((key, n),))

    def add_many(self, items):
        """一次给多个键记账，全部落在同一个桶里。

        items 是 (key, n) 的可迭代对象。同一批 span 的 total 和 sampled
        走这里记账，避免两次写之间窗口滚动把账拆到两批桶上。
        """
        now = self._clock()
        with self._lock:
            self._rotate(now)
            bucket = self._buckets[self._current % self._bucket_count]
            for key, n in items:
                if n:
                    bucket[key] = bucket.get(key, 0) + n

    def count(self, key):
        """窗口内 key 的合计条数。"""
        return self.snapshot((key,))[key]

    def snapshot(self, keys):
        """一次读出多个键在窗口内的合计，键之间读的是同一批桶。"""
        now = self._clock()
        totals = dict.fromkeys(keys, 0)
        with self._lock:
            self._rotate(now)
            for bucket in self._buckets:
                for key in totals:
                    totals[key] += bucket.get(key, 0)
        return totals

    def per_second(self, key):
        """窗口内 key 的每秒均值。"""
        return self.count(key) / self._window_seconds

    def rates(self, keys):
        """多键的每秒均值，按统计实际覆盖的时长换算。

        冷启动或长时间空闲后窗口还没被数据填满，按 window_seconds 硬除会
        系统性低估吞吐，这里按现存桶实际覆盖的时间长度（封顶一个窗口）来
        折算每秒均值。
        """
        now = self._clock()
        totals = dict.fromkeys(keys, 0)
        with self._lock:
            self._rotate(now)
            oldest_nonempty = None
            oldest = self._current - self._bucket_count + 1
            for offset in range(self._bucket_count):
                index = oldest + offset
                bucket = self._buckets[index % self._bucket_count]
                if bucket and oldest_nonempty is None:
                    oldest_nonempty = index
                if bucket:
                    for key in totals:
                        totals[key] += bucket.get(key, 0)
            if oldest_nonempty is None:
                covered = self._bucket_seconds
            else:
                elapsed_in_current = now - self._current * self._bucket_seconds
                covered = ((self._current - oldest_nonempty)
                           * self._bucket_seconds + elapsed_in_current)
                if covered <= 0:
                    covered = self._bucket_seconds
                covered = min(covered, self._window_seconds)
        return {key: totals[key] / covered for key in totals}

    def reset(self):
        """清空所有桶。"""
        with self._lock:
            for bucket in self._buckets:
                bucket.clear()
            self._current = int(self._clock() / self._bucket_seconds)

    # ---- 内部实现 ----

    def _rotate(self, now):
        """时钟进了新的桶格就滚一下窗口。"""
        index = int(now / self._bucket_seconds)
        if index == self._current:
            return
        elapsed_buckets = index - self._current
        if elapsed_buckets >= self._bucket_count:
            # 跨过了一整个窗口，旧账全部过期
            for bucket in self._buckets:
                bucket.clear()
        else:
            # 只清空已经滑出窗口的那几格，其余桶继续算数
            for offset in range(1, elapsed_buckets + 1):
                stale = self._buckets[
                    (self._current + offset) % self._bucket_count]
                stale.clear()
        self._current = index
