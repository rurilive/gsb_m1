"""令牌桶实现：匀速补充、按需扣减，供网关各路由做配额控制。"""
import threading
from typing import Optional

from .clock import Clock, SystemClock


class RateLimitError(RuntimeError):
    """配额不足。"""


class TokenBucket:
    """令牌桶：令牌按 rate 个/秒匀速补充，桶容量上限为 burst。

    时间统一从注入的 Clock 读取，测试可换 FakeClock 手动推进。
    """

    def __init__(self, rate: float, burst: float, clock: Optional[Clock] = None):
        if rate <= 0 or burst <= 0:
            raise ValueError("rate 和 burst 必须为正数")
        self.rate = float(rate)
        self.burst = float(burst)
        self._capacity = self.burst
        self._clock = clock if clock is not None else SystemClock()
        self._tokens = self.burst
        self._last = self._clock.time()
        self._lock = threading.Lock()

    def available(self) -> float:
        """当前余额（触发一次惰性补充）。"""
        with self._lock:
            self._refill(self._clock.time())
            return self._tokens

    def try_allow(self, cost: float = 1.0) -> bool:
        """余额够扣则扣掉并返回 True，否则返回 False。"""
        with self._lock:
            self._refill(self._clock.time())
            if self._tokens < cost:
                return False
            self._tokens -= cost
            return True

    def allow(self, cost: float = 1.0) -> None:
        """语义同 try_allow，余额不足时抛 RateLimitError。"""
        if not self.try_allow(cost):
            raise RateLimitError("令牌不足: 需要 %.1f, 剩余 %.1f" % (cost, self.available()))

    # ---- 内部实现 ----

    def _refill(self, now: float) -> None:
        """按流逝时间补充令牌，调用方需持有锁。"""
        elapsed = now - self._last
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self.rate)
        self._last = now
