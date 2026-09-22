"""接入层用的进程内解析缓存。

命中直接返回地址；没命中打一次上游，把应答连同 TTL 记进字典。
读路径上的过期判断很简单：拿注入时钟的读数和条目的到期时刻比一下，
过期就当成没命中，重新拉一次覆盖掉旧条目。
"""

import threading

from .clock import SystemClock
from .upstream import UpstreamError

DEFAULT_TTL = 30.0


class ResolverCache:
    """域名到地址的进程内缓存。

    upstream: 提供 resolve(name) -> Answer 的对象，生产接真实解析服务，
        测试和演示注入假上游。
    clock: 返回当前时刻的可调用对象，默认单调时钟。
    default_ttl: 上游没给 TTL 时用的默认有效期秒数。
    """

    def __init__(self, upstream, clock=SystemClock(), default_ttl=DEFAULT_TTL):
        if default_ttl < 0:
            raise ValueError("default_ttl must be >= 0")
        self._upstream = upstream
        self._clock = clock
        self._default_ttl = float(default_ttl)
        self._lock = threading.Lock()
        # name -> (address, expires_at)
        self._entries = {}
        self._hits = 0
        self._misses = 0
        self._upstream_calls = 0
        self._errors = 0

    def lookup(self, name):
        """解析域名，返回地址；上游失败时抛 UpstreamError。"""
        with self._lock:
            entry = self._entries.get(name)
            if entry is not None and self._clock() > entry[1]:
                entry = None
            if entry is not None:
                self._hits += 1
                return entry[0]
            self._misses += 1
            self._upstream_calls += 1
        try:
            answer = self._upstream.resolve(name)
        except UpstreamError:
            with self._lock:
                self._errors += 1
            raise
        ttl = self._default_ttl if answer.ttl is None else answer.ttl
        with self._lock:
            self._entries[name] = (answer.address, self._clock() + ttl)
        return answer.address

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "upstream_calls": self._upstream_calls,
                "errors": self._errors,
                "entries": len(self._entries),
            }
