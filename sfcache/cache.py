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
    - invalidate(key)：删除该 key 的缓存条目。回源失败不落缓存，
      下一次 get 会重新回源，因此没有需要清除的失败标记。
    - loads：累计成功回源次数。
    """

    def __init__(self, loader, ttl=None, clock=time.monotonic):
        self._loader = loader
        self._ttl = ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._data = {}      # key -> (value, expire_at)
        self._flights = {}   # key -> _Flight：该 key 上正在进行的回源
        self.loads = 0

    # -- 对外接口 --

    def get(self, key):
        with self._lock:
            flight = self._flights.get(key)
            entry = self._data.get(key)
            if (
                flight is None
                and entry is not None
                and (self._ttl is None or entry[1] > self._clock())
            ):
                # 命中且未过期
                return entry[0]
            if flight is not None:
                # 同 key 已有回源在进行（未命中或条目过期），挂到这一趟上
                leader = False
            else:
                # 未命中或条目已过期：成为这一趟回源的 leader。
                # 过期条目先摘掉，否则 leader 加载期间后来者会把旧值当新值读出。
                flight = _Flight()
                self._flights[key] = flight
                self._data.pop(key, None)
                leader = True
        if leader:
            return self._lead(key, flight)
        flight.done.wait()
        # error/value 都在 done 置位之前发布，这里读到的必是这一趟的结果
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
        # 先发布 value 再唤醒等待者，避免跟随者醒来读到未写入的 None/旧值。
        flight.value = value
        with self._lock:
            if self._flights.get(key) is flight:
                self._flights.pop(key)
            self.loads += 1
            expire_at = None if self._ttl is None else self._clock() + self._ttl
            self._data[key] = (value, expire_at)
        flight.done.set()

    def _fail(self, key, flight, exc):
        # 失败不落缓存：摘掉这一趟 flight，下一次 get 会重新回源。
        with self._lock:
            if self._flights.get(key) is flight:
                self._flights.pop(key)
        # error 先于 done 发布，等待者醒来后拿到的就是这一趟的异常。
        flight.error = exc
        flight.done.set()
