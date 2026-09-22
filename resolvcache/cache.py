"""接入层用的进程内解析缓存。

命中直接返回地址；没命中打一次上游，把应答连同 TTL 记进字典。

有效期策略（成功和失败分开）：
- 成功应答记正缓存，TTL 用上有给的，没有就用 default_ttl，并叠加抖动。
- 上游失败记一笔短的负缓存（negative_ttl），有效期内同样的名字直接
  抛上次的错，不再打上游。
- 到 TTL 一半进入"软过期"：读请求先拿旧值，同时只放一个后台请求去
  预刷新；刷新失败就继续拿旧值顶到硬过期，到点了才同步回源。

并发：同一个名字同一时刻只放一个请求去上游，其余线程等这一份结果；
上游失败时错误广播给所有等待者。

边界规则（README 里有同样一份）：
- 到期判定是 now >= expires_at 算硬过期，到点那一刻就算过期。
- 时钟回拨按新读数重算，不删条目、不补 TTL：读回去旧条目可能重新
  变新鲜，这是对注入时钟读数的直接反映。
- TTL 为 0（含 default_ttl/negative_ttl 为 0）表示这次结果不落缓存，
  下一个请求照常回源；并发的那一批仍由 single-flight 合并。
"""

import threading
import random

from .clock import SystemClock
from .upstream import UpstreamError

DEFAULT_TTL = 30.0
DEFAULT_NEGATIVE_TTL = 5.0
DEFAULT_JITTER = 0.1
REFRESH_FRACTION = 0.5


class _Entry:
    """一条缓存记录，正缓存和负缓存共用。

    address 不为 None 是正缓存；error 不为 None 是负缓存（错误实例）。
    soft_at 是进入软过期（开始后台预刷新）的时刻，expires_at 是硬过期。
    只有正缓存使用 soft_at；负缓存没有旧值可顶，直接活到 expires_at。
    """

    __slots__ = ("address", "error", "soft_at", "expires_at",
                 "refresh_tried")

    def __init__(self, address, error, soft_at, expires_at):
        self.address = address
        self.error = error
        self.soft_at = soft_at
        self.expires_at = expires_at
        # 软过期窗口里后台预刷新是否已经失败过一次；失败后不再补刷，
        # 旧值一直顶到硬过期，避免上游抖动时在旧值窗口里反复回源。
        self.refresh_tried = False


class _Flight:
    """同一个名字在飞的唯一一次上游请求，等待者在事件上等结果。"""

    __slots__ = ("event", "address", "error")

    def __init__(self):
        self.event = threading.Event()
        self.address = None
        self.error = None


class ResolverCache:
    """域名到地址的进程内缓存。

    upstream: 提供 resolve(name) -> Answer 的对象，生产接真实解析服务，
        测试和演示注入假上游。
    clock: 返回当前时刻的可调用对象，默认单调时钟。
    default_ttl: 上游没给 TTL 时用的默认有效期秒数。
    negative_ttl: 上游失败的负缓存有效期秒数，和正缓存分开配。
    jitter: 有效期抖动幅度，0~1 之间的比例；实际 TTL 在
        ttl*(1±jitter) 之间取值，0 表示不加抖动。
    rng: 抖动用的随机源，需要 random.Random 同接口的对象，默认新建一个
        random.Random()；测试里注入固定种子保证可复现。
    """

    def __init__(self, upstream, clock=SystemClock(), default_ttl=DEFAULT_TTL,
                 *, negative_ttl=DEFAULT_NEGATIVE_TTL,
                 jitter=DEFAULT_JITTER, rng=None):
        if default_ttl < 0:
            raise ValueError("default_ttl must be >= 0")
        if negative_ttl < 0:
            raise ValueError("negative_ttl must be >= 0")
        if not 0.0 <= jitter <= 1.0:
            raise ValueError("jitter must be between 0.0 and 1.0")
        self._upstream = upstream
        self._clock = clock
        self._default_ttl = float(default_ttl)
        self._negative_ttl = float(negative_ttl)
        self._jitter = float(jitter)
        self._rng = rng if rng is not None else random.Random()
        self._lock = threading.Lock()
        # name -> _Entry
        self._entries = {}
        # name -> _Flight：在飞的请求（同步回源和后台预刷新共用同一航班）
        self._flights = {}
        # 正在后台预刷新的名字集合
        self._refreshing = set()
        self._hits = 0
        self._misses = 0
        self._upstream_calls = 0
        self._errors = 0

    def lookup(self, name):
        """解析域名，返回地址；上游失败时抛 UpstreamError。

        同一个名字并发到来时只有一个线程打上游，其余等这份结果；
        正缓存软过期时先返回旧值并放后台预刷新；失败（负缓存命中、
        硬过期回源失败、等待者收到广播）计 errors 并把错抛给调用方。
        """
        with self._lock:
            now = self._clock()
            entry = self._entries.get(name)
            if entry is not None:
                if entry.address is not None:
                    # 正缓存：soft_at 前直接命中。
                    if now < entry.soft_at:
                        self._hits += 1
                        return entry.address
                    # 软过期到硬过期之间：旧值先顶着，只放一个后台刷新。
                    if now < entry.expires_at:
                        self._hits += 1
                        if not entry.refresh_tried:
                            self._spawn_refresh_locked(name)
                        return entry.address
                elif now < entry.expires_at:
                    # 负缓存有效期内：直接把记着的错抛出去。
                    self._hits += 1
                    self._errors += 1
                    error = entry.error
                    raise error

            # 到这里需要一份新结果：有航班就等，没有自己当 leader。
            flight = self._flights.get(name)
            if flight is None:
                flight = _Flight()
                self._flights[name] = flight
                leader = True
            else:
                leader = False
            self._misses += 1
            if leader:
                self._upstream_calls += 1

        if not leader:
            flight.event.wait()
            if flight.error is not None:
                with self._lock:
                    self._errors += 1
                raise flight.error
            return flight.address

        try:
            answer = self._upstream.resolve(name)
        except Exception as exc:
            self._settle_failure(name, exc)
            with self._lock:
                self._errors += 1
            raise
        self._settle_success(name, answer)
        return answer.address

    def _spawn_refresh_locked(self, name):
        """放一个后台预刷新（调用时已持锁）；已有航班就不重复放。"""
        if name in self._flights or name in self._refreshing:
            return
        self._flights[name] = _Flight()
        thread = threading.Thread(
            target=self._run_background_refresh, args=(name,),
            name="resolvcache-refresh-%s" % name, daemon=True)
        self._refreshing.add(name)
        self._upstream_calls += 1
        thread.start()

    def _run_background_refresh(self, name):
        """后台航班：成功换条目，失败让旧值继续顶到硬过期。"""
        try:
            answer = self._upstream.resolve(name)
        except Exception as exc:
            self._settle_failure(name, exc)
            return
        self._settle_success(name, answer)

    def _settle_success(self, name, answer):
        """航班成功：落正缓存（零 TTL 不落），唤醒所有等待者。"""
        with self._lock:
            self._refreshing.discard(name)
            ttl = (self._default_ttl if answer.ttl is None
                   else float(answer.ttl))
            if ttl > 0:
                self._entries[name] = self._make_entry_locked(
                    answer.address, None, ttl)
            else:
                self._entries.pop(name, None)
            flight = self._flights.pop(name, None)
            if flight is not None:
                flight.address = answer.address
                flight.event.set()

    def _settle_failure(self, name, exc):
        """航班失败：旧正缓存还没硬过期就继续顶，否则记一笔负缓存。"""
        with self._lock:
            self._refreshing.discard(name)
            now = self._clock()
            entry = self._entries.get(name)
            keep_stale = (entry is not None and entry.address is not None
                          and now < entry.expires_at)
            if not keep_stale:
                if isinstance(exc, UpstreamError) and self._negative_ttl > 0:
                    self._entries[name] = self._make_entry_locked(
                        None, exc, self._negative_ttl)
                else:
                    # 非 UpstreamError 不缓存，或负 TTL 为 0：下次重查。
                    self._entries.pop(name, None)
            else:
                entry.refresh_tried = True
            flight = self._flights.pop(name, None)
            if flight is not None:
                flight.error = exc
                flight.event.set()

    def _make_entry_locked(self, address, error, ttl):
        """按当前时钟读数和抖动造一条记录（调用时已持锁）。"""
        now = self._clock()
        effective = ttl * (1.0 + self._jittered_locked())
        return _Entry(address, error,
                      now + effective * REFRESH_FRACTION, now + effective)

    def _jittered_locked(self):
        """返回 [-jitter, jitter] 区间的抖动系数；jitter 为 0 时恒为 0。"""
        if self._jitter == 0.0:
            return 0.0
        return self._rng.random() * 2.0 * self._jitter - self._jitter

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "upstream_calls": self._upstream_calls,
                "errors": self._errors,
                "entries": len(self._entries),
                "refreshing": len(self._refreshing),
            }
