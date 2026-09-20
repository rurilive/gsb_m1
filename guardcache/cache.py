"""进程内多级缓存，带加载函数回填。

命中直接返回，未命中调用 loader 回填并把结果写进缓存；主层条目带存活
时间（TTL，写入时一次性算好，读取不续期），超出容量按 LRU 驱逐，驱逐
时优先挤掉正条目、保护负条目；loader 报不存在时记入负缓存，回源报其它
异常时不写任何条目。同一个 key 的并发未命中只放一个 loader 出去，其余
请求等同一趟结果，避免惊群和慢请求旧值覆盖。纯标准库实现，时间读取
统一走注入的 clock。
"""

import threading
import time
from collections import OrderedDict


class NotFound(Exception):
    """loader 用它表示 key 不存在，缓存据此记录负条目。"""


class _Missing:
    """负缓存的占位标记。"""

    __slots__ = ()

    def __repr__(self):
        return "<missing>"


_MISSING = _Missing()


class _Entry:
    """一条缓存记录。

    value 为 _MISSING 时表示负条目；expires_at 为 None 表示不过期。
    """

    __slots__ = ("value", "expires_at")

    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at


class _Flight:
    """同一个 key 正在回源时的共享航班：并发未命中只跑一个 loader。"""

    __slots__ = ("event", "value", "error")

    def __init__(self):
        self.event = threading.Event()
        self.value = None
        self.error = None


class GuardCache:
    """两级缓存 + 回源加载。

    capacity: 主层最大条目数，超出后按 LRU 驱逐。
    ttl: 正条目存活秒数；None 表示永不过期。
    negative_ttl: 负条目存活秒数；None 表示永不过期。
    hot_capacity: 热层最大条目数，默认与 capacity 相同。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, loader, ttl=None, capacity=128, negative_ttl=30,
                 hot_capacity=None, clock=time.monotonic):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._loader = loader
        self._ttl = ttl
        self._negative_ttl = negative_ttl
        self._capacity = capacity
        self._hot_capacity = capacity if hot_capacity is None else hot_capacity
        if self._hot_capacity < 1:
            raise ValueError("hot_capacity must be >= 1")
        self._clock = clock
        self._lock = threading.Lock()
        self._main = OrderedDict()   # key -> _Entry，主层
        self._hot = OrderedDict()    # key -> _Entry，热层，与主层共享同一对象
        self._inflight = {}          # key -> _Flight，回源中的 key
        self._hits = 0
        self._misses = 0
        self._loads = 0
        self._evicted = 0
        self._negatives = 0

    # -- 对外接口 --

    def get(self, key):
        """命中返回缓存值；负条目命中抛 NotFound；未命中回源加载。"""
        with self._lock:
            entry = self._hot.get(key)
            if entry is not None:
                if not self._expired(entry):
                    self._hot.move_to_end(key)
                    if key in self._main:
                        self._main.move_to_end(key)
                    self._hits += 1
                    if entry.value is _MISSING:
                        raise NotFound(key)
                    return entry.value
                self._hot.pop(key, None)
            entry = self._main.get(key)
            if entry is not None:
                if not self._expired(entry):
                    self._main.move_to_end(key)
                    self._promote(key, entry)
                    self._hits += 1
                    if entry.value is _MISSING:
                        raise NotFound(key)
                    return entry.value
                self._main.pop(key, None)
            self._misses += 1
            flight = self._inflight.get(key)
            if flight is None:
                # 本趟回源由当前请求领头，其它同 key 的未命中搭航班
                flight = _Flight()
                self._inflight[key] = flight
                leader = True
                self._loads += 1
            else:
                leader = False
        if not leader:
            flight.event.wait()
            if flight.error is not None:
                raise flight.error
            return flight.value
        return self._load(key, flight)

    def invalidate(self, key):
        """删除该 key 的正/负缓存条目，返回是否真的删掉了。"""
        with self._lock:
            existed = key in self._main
            self._main.pop(key, None)
            self._hot.pop(key, None)
            return existed

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "loads": self._loads,
                "evicted": self._evicted,
                "negatives": self._negatives,
            }

    # -- 内部实现 --

    def _load(self, key, flight):
        """领头回源。调用时不在持锁状态，loader 可以慢慢跑。

        结果（值或异常）发布到航班上，等待中的同 key 请求共享同一趟
        结果。只有成功和 NotFound 会写缓存；其它异常不留下任何条目，
        下次 get 自然重新回源，不会把坏值钉在缓存里。
        """
        try:
            value = self._loader(key)
        except NotFound as exc:
            self._remember(key, _MISSING)
            with self._lock:
                self._negatives += 1
            flight.error = exc
        except Exception as exc:
            flight.error = exc
        else:
            self._remember(key, value)
            flight.value = value
        finally:
            with self._lock:
                # 先放行等待者再摘除航班：成功时缓存已在 _remember 里
                # 落盘，失败时航班还在字典里，新来的请求只会搭旧航班，
                # 不会在这个缝隙里重复回源
                flight.event.set()
                if self._inflight.get(key) is flight:
                    del self._inflight[key]
        if flight.error is not None:
            raise flight.error
        return flight.value

    def _remember(self, key, value):
        with self._lock:
            entry = _Entry(value, self._fresh_expiry(value))
            self._main.pop(key, None)
            self._main[key] = entry
            self._promote(key, entry)
            while len(self._main) > self._capacity:
                evicted_key = self._evict_lru(self._main)
                self._hot.pop(evicted_key, None)
                self._evicted += 1

    def _promote(self, key, entry):
        """把条目放进热层。调用时需持有锁。"""
        self._hot.pop(key, None)
        self._hot[key] = entry
        while len(self._hot) > self._hot_capacity:
            self._evict_lru(self._hot)

    @staticmethod
    def _evict_lru(layer):
        """按 LRU 选一个牺牲者并驱逐，返回它的 key。

        负条目是“确认不存在”的占位，被挤掉后同一个幽灵 key 又会反复
        打下游，所以驱逐时先挑最久未用的正条目；整层全是负条目时才
        退回最旧的负条目。调用时需持有锁。
        """
        victim = None
        for candidate, entry in layer.items():
            if entry.value is not _MISSING:
                victim = candidate
                break
        if victim is None:
            victim, _ = layer.popitem(last=False)
        else:
            layer.pop(victim)
        return victim

    def _fresh_expiry(self, value):
        ttl = self._negative_ttl if value is _MISSING else self._ttl
        if ttl is None:
            return None
        return self._clock() + ttl

    def _expired(self, entry):
        return entry.expires_at is not None and entry.expires_at <= self._clock()
