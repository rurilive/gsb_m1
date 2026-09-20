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

    def add_many(self, counts):
        """一次性记多个 key，各自加对应的条数。

        一次加锁完成，保证这批计数落在同一个桶里，读快照时不会把一组
        同时发生的计数读成两半。
        """
        if not counts:
            return
        now = self._clock()
        with self._lock:
            self._rotate(now)
            bucket = self._buckets[self._current % self._bucket_count]
            for key, n in counts.items():
                bucket[key] = bucket.get(key, 0) + n

    def snapshot(self, keys=()):
        """同一把锁里读出多个 key 的窗口合计，返回 {key: 条数}。

        决策控制需要 total 和 sampled 两个数，必须保证它们来自同一个
        窗口状态；分开两次 count 可能正好撞上滚桶，把两个计数读岔。
        """
        now = self._clock()
        with self._lock:
            self._rotate(now)
            return {key: sum(bucket.get(key, 0) for bucket in self._buckets)
                    for key in keys}

    def count(self, key):
        """窗口内 key 的合计条数。"""
        now = self._clock()
        with self._lock:
            self._rotate(now)
            return sum(bucket.get(key, 0) for bucket in self._buckets)

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
        elapsed = index - self._current
        if elapsed <= 0:
            return
        if elapsed >= self._bucket_count:
            # 空窗时间超过一整个窗口，所有桶都过期了
            for bucket in self._buckets:
                bucket.clear()
        else:
            # 只清已经滑出窗口的老桶，最近的桶原样保留
            for slot in range(elapsed):
                self._buckets[(self._current + 1 + slot)
                              % self._bucket_count].clear()
        self._current = index
