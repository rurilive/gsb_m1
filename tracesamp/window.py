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
        self._buckets = [dict() for _ in range(self._bucket_count)]
        self._current = int(clock() / self._bucket_seconds)
        self._born = clock()

    @property
    def window_seconds(self):
        return self._window_seconds

    def add(self, key, n=1):
        """给 key 记 n 条，记在当前桶里。"""
        now = self._clock()
        with self._lock:
            self._rotate(now)
            bucket = self._buckets[self._current % self._bucket_count]
            bucket[key] = bucket.get(key, 0) + n

    def count(self, key):
        """窗口内 key 的合计条数。"""
        now = self._clock()
        with self._lock:
            self._rotate(now)
            return sum(bucket.get(key, 0) for bucket in self._buckets)

    def counts(self, keys):
        """一把锁里读出多个 key 的窗口合计，返回 {key: 条数}。

        多个计数要拿同一时刻的窗口读数时用它，分两次调 count 中间可能
        隔着一次滚动，两个数就对不上了。
        """
        now = self._clock()
        with self._lock:
            self._rotate(now)
            return {key: sum(bucket.get(key, 0) for bucket in self._buckets)
                    for key in keys}

    def readings(self, keys):
        """一把锁里读出多个 key 的窗口合计和窗口当前实际覆盖的秒数。

        桶是对齐到固定刻度的，窗口实际覆盖的时长在
        [window_seconds - 一格, window_seconds] 之间浮动；算每秒速率时拿
        合计除以这个真实覆盖时长，才不会跟着桶的相位系统性偏小。
        """
        now = self._clock()
        with self._lock:
            self._rotate(now)
            counts = {key: sum(bucket.get(key, 0) for bucket in self._buckets)
                      for key in keys}
            oldest = (self._current - self._bucket_count + 1) \
                * self._bucket_seconds
            covered = now - max(oldest, self._born)
            covered = min(self._window_seconds,
                          max(covered, self._bucket_seconds))
            return counts, covered

    def per_second(self, key):
        """窗口内 key 的每秒均值。"""
        return self.count(key) / self._window_seconds

    def reset(self):
        """清空所有桶。"""
        with self._lock:
            for bucket in self._buckets:
                bucket.clear()

    # ---- 内部实现 ----

    def _rotate(self, now):
        """时钟进了新的桶格就滚一下窗口。"""
        index = int(now / self._bucket_seconds)
        if index == self._current:
            return
        if index - self._current >= self._bucket_count:
            # 空闲太久，整窗都过期了
            for bucket in self._buckets:
                bucket.clear()
        else:
            # 只清掉被新格复用的那只桶，其余桶里的数据还在窗口内
            for step in range(self._current + 1, index + 1):
                self._buckets[step % self._bucket_count].clear()
        self._current = index
