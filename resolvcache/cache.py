"""接入层用的进程内解析缓存。

命中直接返回地址；没命中时同一个域名只放一路请求回源，其余线程挂在
这次请求上等结果，上游失败时错误广播给所有等待者。上游失败会记一笔
短期负缓存，有效期跟成功条目分开配置。正向条目在有效期过半后由后台
线程预刷新，刷新失败时旧值继续顶到硬过期。所有有效期都可以加抖动，
避免条目集中到期一起失效。

边界规则（详见 README）：
- 到点那一刻仍算命中，时钟读数严格大于到期时刻才算过期；
- 时钟回拨（读数小于此前见过的最大读数）时全部条目立即失效；
- 上游给零或负 TTL 的应答不落缓存，每次 lookup 都回源。
"""

import random
import threading

from .clock import SystemClock
from .upstream import UpstreamError

DEFAULT_TTL = 30.0
DEFAULT_NEGATIVE_TTL = 5.0
DEFAULT_JITTER = 0.0


class _Entry:
    """一条缓存记录。error 非空表示负缓存条目，命中时抛出它。"""

    __slots__ = ("address", "error", "expires_at", "refresh_at", "refreshing")

    def __init__(self, address, error, expires_at, refresh_at):
        self.address = address
        self.error = error
        self.expires_at = expires_at
        self.refresh_at = refresh_at
        self.refreshing = False


class _Flight:
    """一次进行中的回源请求，同名并发 lookup 的等待者挂在 done 上。"""

    __slots__ = ("done", "address", "error")

    def __init__(self):
        self.done = threading.Event()
        self.address = None
        self.error = None


class ResolverCache:
    """域名到地址的进程内缓存。

    upstream: 提供 resolve(name) -> Answer 的对象，生产接真实解析服务，
        测试和演示注入假上游。
    clock: 返回当前时刻的可调用对象，默认单调时钟。
    default_ttl: 上游没给 TTL 时用的默认有效期秒数。
    negative_ttl: 上游失败时负缓存的有效期秒数，0 表示关掉负缓存。
    jitter: 有效期抖动幅度，实际有效期乘上 1±jitter 的随机因子。
    rng: 抖动用的随机源，需有 uniform(a, b)；测试注入固定种子的
        random.Random 即可复现。
    refresh: 是否在有效期过半后后台预刷新，默认开。
    """

    def __init__(self, upstream, clock=SystemClock(), default_ttl=DEFAULT_TTL,
                 *, negative_ttl=DEFAULT_NEGATIVE_TTL,
                 jitter=DEFAULT_JITTER, rng=None, refresh=True):
        if default_ttl < 0:
            raise ValueError("default_ttl must be >= 0")
        if negative_ttl < 0:
            raise ValueError("negative_ttl must be >= 0")
        if not 0.0 <= jitter < 1.0:
            raise ValueError("jitter must be in [0, 1)")
        self._upstream = upstream
        self._clock = clock
        self._default_ttl = float(default_ttl)
        self._negative_ttl = float(negative_ttl)
        self._jitter = float(jitter)
        self._rng = rng if rng is not None else random
        self._refresh_enabled = bool(refresh)
        self._lock = threading.Lock()
        # name -> _Entry
        self._entries = {}
        # name -> _Flight，进行中的回源请求
        self._inflight = {}
        self._last_now = None
        self._hits = 0
        self._misses = 0
        self._upstream_calls = 0
        self._errors = 0

    def lookup(self, name):
        """解析域名，返回地址；上游失败时抛 UpstreamError。"""
        with self._lock:
            now = self._now_locked()
            entry = self._entries.get(name)
            if entry is not None and now > entry.expires_at:
                del self._entries[name]
                entry = None
            if entry is not None:
                self._hits += 1
                self._maybe_refresh_locked(name, entry, now)
                if entry.error is not None:
                    raise entry.error
                return entry.address
            flight = self._inflight.get(name)
            if flight is None:
                flight = _Flight()
                self._inflight[name] = flight
                self._misses += 1
                self._upstream_calls += 1
                leader = True
            else:
                leader = False
        if not leader:
            # 同名回源已在进行，等它的结果，不再打上游。
            flight.done.wait()
            with self._lock:
                self._hits += 1
            if flight.error is not None:
                raise flight.error
            return flight.address
        try:
            answer = self._upstream.resolve(name)
        except UpstreamError as exc:
            with self._lock:
                self._errors += 1
                self._inflight.pop(name, None)
                self._store_negative_locked(name, exc)
                flight.error = exc
                flight.done.set()
            raise
        except BaseException as exc:
            with self._lock:
                self._inflight.pop(name, None)
                flight.error = exc
                flight.done.set()
            raise
        ttl = self._default_ttl if answer.ttl is None else answer.ttl
        with self._lock:
            self._inflight.pop(name, None)
            self._store_positive_locked(name, answer.address, ttl)
            flight.address = answer.address
            flight.done.set()
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

    def _now_locked(self):
        """读注入时钟；发现回拨就清空全部条目，从回拨后的读数重新计。"""
        now = self._clock()
        if self._last_now is not None and now < self._last_now:
            self._entries.clear()
        self._last_now = now
        return now

    def _jittered(self, ttl):
        if self._jitter <= 0.0:
            return ttl
        return ttl * (1.0 + self._rng.uniform(-self._jitter, self._jitter))

    def _store_positive_locked(self, name, address, ttl):
        if ttl <= 0:
            # 上游给零/负 TTL：不落缓存，每次 lookup 都回源。
            self._entries.pop(name, None)
            return
        now = self._now_locked()
        effective = self._jittered(ttl)
        self._entries[name] = _Entry(
            address=address, error=None,
            expires_at=now + effective,
            refresh_at=now + effective / 2.0)

    def _store_negative_locked(self, name, error):
        if self._negative_ttl <= 0:
            return
        now = self._now_locked()
        effective = self._jittered(self._negative_ttl)
        self._entries[name] = _Entry(
            address=None, error=error,
            expires_at=now + effective,
            refresh_at=float("inf"))

    def _maybe_refresh_locked(self, name, entry, now):
        """正向条目过了有效期一半就起后台预刷新，每条目同时只刷一路。"""
        if (not self._refresh_enabled or entry.error is not None
                or entry.refreshing or now < entry.refresh_at):
            return
        entry.refreshing = True
        self._upstream_calls += 1
        thread = threading.Thread(target=self._refresh, args=(name,))
        thread.daemon = True
        thread.start()

    def _refresh(self, name):
        """后台预刷新：成功换上新应答，失败保留旧条目顶到硬过期。"""
        try:
            answer = self._upstream.resolve(name)
        except UpstreamError:
            with self._lock:
                self._errors += 1
                entry = self._entries.get(name)
                if entry is not None and entry.refreshing:
                    entry.refreshing = False
                    # 不再重试，旧值顶到硬过期后按未命中重新回源。
                    entry.refresh_at = entry.expires_at
            return
        except BaseException:
            with self._lock:
                entry = self._entries.get(name)
                if entry is not None and entry.refreshing:
                    entry.refreshing = False
                    entry.refresh_at = entry.expires_at
            return
        ttl = self._default_ttl if answer.ttl is None else answer.ttl
        with self._lock:
            self._store_positive_locked(name, answer.address, ttl)
