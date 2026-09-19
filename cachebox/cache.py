"""进程内 LRU 缓存。

固定容量，超出后按 LRU 顺序驱逐；命中、未命中、驱逐
计数统一在 stats() 里汇总。
"""

import threading
import time
from collections import OrderedDict


class LRUCache:
    """固定容量的 LRU 缓存。

    capacity: 最大条目数，超过后驱逐最久未使用的条目。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, capacity, clock=time.monotonic):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (value, expires_at)；expires_at 为 None 表示没有过期时间
        self._entries = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evicted = 0

    def set(self, key, value):
        """写入条目。已存在的 key 覆盖值并刷新为最近使用。"""
        with self._lock:
            if key in self._entries:
                del self._entries[key]
            self._entries[key] = (value, None)
            while len(self._entries) > self._capacity:
                self._entries.popitem(last=False)
                self._evicted += 1

    def get(self, key):
        """读取条目，未命中返回 None。"""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return entry[0]

    def delete(self, key):
        """删除条目，返回是否真的删掉了。"""
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evicted": self._evicted,
            }
