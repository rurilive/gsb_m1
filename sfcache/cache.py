"""带单飞（singleflight）合并的缓存加载器。

命中且未过期直接返回；未命中则回源加载并写入缓存。同一个 key 上
并发到达的请求合并成一次回源，共享同一份结果。纯标准库实现。
"""
import threading
import time


class _Flight:
    """一个 key 上正在进行的一次回源。"""

    __slots__ = ("done", "value", "error")

    def __init__(self):
        self.done = threading.Event()
        self.value = None
        self.error = None


class Cache:
    """缓存 + 回源 + 并发合并。

    - get(key)：命中且未过期直接返回；否则回源加载后写入缓存。
    - ttl：条目存活秒数；None 表示永不过期。
    - invalidate(key)：删除该 key 的缓存条目，并清除它的失败标记。
    - loads：累计回源次数。
    """

    def __init__(self, loader, ttl=None, clock=time.monotonic):
        self._loader = loader
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._data = {}      # key -> (value, expire_at)
        self._flights = {}   # key -> 该 key 上正在进行的回源
        self._failed = {}    # key -> 最近一次回源异常
        self.loads = 0

    # -- 对外接口 --

    def get(self, key):
        with self._lock:
            if key in self._failed:
                raise self._failed[key]
            if key in self._data:
                value, expire_at = self._data[key]
                if self._ttl is None or expire_at > self._clock():
                    return value
                # 条目已过期，重新加载
                flight = _Flight()
                leader = True
            else:
                flight = self._flights.get(key)
                if flight is None:
                    flight = _Flight()
                    self._flights[key] = flight
                    leader = True
                else:
                    leader = False
        if leader:
            return self._lead(key, flight)
        flight.done.wait()
        if flight.error is not None:
            raise flight.error
        return flight.value

    def invalidate(self, key):
        with self._lock:
            self._data.pop(key, None)

    # -- 内部实现 --

    def _lead(self, key, flight):
        try:
            value = self._loader(key)
        except Exception as exc:
            self._fail(key, flight, exc)
            raise
        self._finish(key, flight, value)
        return value

    def _finish(self, key, flight, value):
        self._flights.pop(key, None)
        flight.done.set()
        with self._lock:
            self.loads += 1
            expire_at = None if self._ttl is None else self._clock() + self._ttl
            self._data[key] = (value, expire_at)
        flight.value = value

    def _fail(self, key, flight, exc):
        self._failed[key] = exc
        flight.error = exc
