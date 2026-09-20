"""进程内多级缓存，带加载函数回填。

命中直接返回，未命中调用 loader 回填并把结果写进缓存；主层条目带存活
时间（TTL），超出容量按 LRU 驱逐；loader 报不存在时记入负缓存。纯标准
库实现，时间读取统一走注入的 clock。
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


_ERROR_TTL = 1.0
"""回源异常占位条目的存活秒数。

短到抖了一下的 key 能快速自愈，又能在下游故障期间挡住同一个 key 的
重复回源。
"""


class _Entry:
    """一条缓存记录。

    value 为 _MISSING 时表示负条目；expires_at 为 None 表示不过期。
    """

    __slots__ = ("value", "expires_at")

    def __init__(self, value, expires_at):
        self.value = value
        self.expires_at = expires_at


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
        self._neg = OrderedDict()    # key -> _Entry，负条目独立容量池
        self._inflight = {}          # key -> threading.Event，在途回源去重
        self._hits = 0
        self._misses = 0
        self._loads = 0
        self._evicted = 0
        self._negatives = 0

    # -- 对外接口 --

    def get(self, key):
        """命中返回缓存值；负条目命中抛 NotFound；未命中回源加载。"""
        while True:
            with self._lock:
                entry = self._hot.get(key)
                if entry is not None:
                    if not self._expired(entry):
                        self._hot.move_to_end(key)
                        if key in self._main:
                            self._main.move_to_end(key)
                        self._hits += 1
                        return entry.value
                    del self._hot[key]
                entry = self._main.get(key)
                if entry is not None:
                    if not self._expired(entry):
                        self._main.move_to_end(key)
                        self._promote(key, entry)
                        self._hits += 1
                        return entry.value
                    del self._main[key]
                entry = self._neg.get(key)
                if entry is not None:
                    if not self._expired(entry):
                        self._neg.move_to_end(key)
                        self._hits += 1
                        raise NotFound(key)
                    del self._neg[key]
                self._misses += 1
                event = self._inflight.get(key)
                if event is None:
                    # 自己是第一个未命中的，负责回源；其余线程等结果
                    event = threading.Event()
                    self._inflight[key] = event
                    break
            # 同一 key 已有在途回源，等它完成后重新走一遍缓存查找
            event.wait()
        try:
            return self._load(key)
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            event.set()

    def invalidate(self, key):
        """删除该 key 的正/负缓存条目，返回是否真的删掉了。"""
        with self._lock:
            existed = key in self._main or key in self._neg
            self._main.pop(key, None)
            self._hot.pop(key, None)
            self._neg.pop(key, None)
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

    def _load(self, key):
        """回源加载。调用时不在持锁状态，loader 可以慢慢跑。"""
        with self._lock:
            self._loads += 1
        try:
            value = self._loader(key)
        except NotFound:
            self._remember(key, _MISSING)
            with self._lock:
                self._negatives += 1
            raise
        except Exception:
            # 回源抖动时先占个位，省得故障期间同一个 key 反复打下游；
            # 占位只留很短时间，之后自动回源重试，不会一直返回空结果
            self._remember(key, None,
                           expires_at=self._clock() + _ERROR_TTL)
            raise
        self._remember(key, value)
        return value

    def _remember(self, key, value, expires_at=None):
        with self._lock:
            if expires_at is None:
                expires_at = self._fresh_expiry(value)
            entry = _Entry(value, expires_at)
            if value is _MISSING:
                # 负条目放独立容量池，不被正常条目挤掉
                self._main.pop(key, None)
                self._hot.pop(key, None)
                self._neg.pop(key, None)
                self._neg[key] = entry
                while len(self._neg) > self._capacity:
                    self._neg.popitem(last=False)
                    self._evicted += 1
                return
            self._neg.pop(key, None)
            self._main.pop(key, None)
            self._main[key] = entry
            self._promote(key, entry)
            while len(self._main) > self._capacity:
                evicted_key, _ = self._main.popitem(last=False)
                self._hot.pop(evicted_key, None)
                self._evicted += 1

    def _promote(self, key, entry):
        """把条目放进热层。调用时需持有锁。"""
        self._hot.pop(key, None)
        self._hot[key] = entry
        while len(self._hot) > self._hot_capacity:
            self._hot.popitem(last=False)

    def _fresh_expiry(self, value):
        ttl = self._negative_ttl if value is _MISSING else self._ttl
        if ttl is None:
            return None
        return self._clock() + ttl

    def _expired(self, entry):
        return entry.expires_at is not None and entry.expires_at <= self._clock()
