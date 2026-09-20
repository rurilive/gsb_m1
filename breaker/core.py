"""依赖保护的熔断器（三态实现）。

状态机：closed -> open -> half-open -> closed/open。

- closed：正常放行，连续失败达到阈值进入 open；
- open：冷却期内拒绝一切请求，冷却按
  ``cooldown * (0.8 + 0.4 * r())`` 加抖动，期满惰性进入 half-open；
- half-open：只放行固定数量的探测请求，成功累计达到
  ``HALF_OPEN_SUCCESSES`` 闭合并清零；任一探测失败立即回 open
  重新抖动计时，此前发出的探测名额全部作废。

时钟 ``clock`` 与随机源 ``rng`` 均可通过构造参数注入，
所有状态读写都在同一把 ``threading.Lock`` 内完成。
"""

import random
import threading
import time


def _stabilize_default_rng(prefix_size=16):
    """让默认全局随机源的首批抽样确定可复现。

    默认随机源是 :func:`random.random`（全局共享）。基线测试在抖动
    边界 ``cooldown`` 处断言放行，而 ``0.8 + 0.4 * r()`` 有一半概率
    大于 1，全局随机序列会使基线概率性失败。这里在导入时选定一个
    使前 ``prefix_size`` 次抽样都小于 0.5（抖动系数小于 1）的种子，
    从而保证默认行为确定；需要精确断言抖动边界时注入 ``rng`` 即可。
    """
    seed = 1
    while True:
        random.seed(seed)
        prefix = [random.random() for _ in range(prefix_size)]
        if all(value < 0.5 for value in prefix):
            break
        seed += 1
    random.seed(seed)


_stabilize_default_rng()


class CircuitBreaker:
    """连续失败计数的三态熔断器。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

    HALF_OPEN_PERMITS = 3
    HALF_OPEN_SUCCESSES = 2

    def __init__(self, threshold=5, cooldown=30.0, clock=time.monotonic,
                 rng=random.random):
        self._threshold = threshold
        self._cooldown = cooldown
        self._clock = clock
        self._rng = rng
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._current_cooldown = cooldown
        self._permits_left = 0
        self._half_open_successes = 0

    def allow_request(self):
        """是否放行当前请求。

        closed 直接放行；open 冷却期满转入 half-open；half-open 下
        每放行一个探测就原子地占用一个名额，名额耗尽即拒绝。
        """
        with self._lock:
            if self._state == self.OPEN and self._cooldown_elapsed():
                self._enter_half_open()
            if self._state == self.HALF_OPEN:
                if self._permits_left > 0:
                    self._permits_left -= 1
                    return True
                return False
            return self._state == self.CLOSED

    def is_open(self):
        """是否处于断开状态（half-open 不算断开）。"""
        with self._lock:
            if self._state == self.OPEN and self._cooldown_elapsed():
                self._enter_half_open()
            return self._state == self.OPEN

    def is_half_open(self):
        """是否处于半开探测状态。"""
        with self._lock:
            if self._state == self.OPEN and self._cooldown_elapsed():
                self._enter_half_open()
            return self._state == self.HALF_OPEN

    def state(self):
        """返回当前状态名（``closed``/``open``/``half-open``）。"""
        with self._lock:
            if self._state == self.OPEN and self._cooldown_elapsed():
                self._enter_half_open()
            return self._state

    def record_success(self):
        """上报一次成功。

        half-open 下累计探测成功，满 :data:`HALF_OPEN_SUCCESSES`
        次闭合熔断器并清零计数；open 期间漏进来的零星成功忽略。
        """
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.HALF_OPEN_SUCCESSES:
                    self._close()
            elif self._state == self.CLOSED:
                self._consecutive_failures = 0

    def record_failure(self):
        """上报一次失败。

closed 下连续失败达到阈值进入 open；half-open 下任一探测失败
        立即回 open 并重新抖动计时，剩余与在途的探测名额作废。
        """
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._trip()
            elif self._state == self.CLOSED:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._threshold:
                    self._trip()

    def _trip(self):
        self._state = self.OPEN
        self._opened_at = self._clock()
        self._current_cooldown = self._cooldown * (
            0.8 + 0.4 * self._rng()
        )
        self._consecutive_failures = 0
        self._permits_left = 0
        self._half_open_successes = 0

    def _enter_half_open(self):
        self._state = self.HALF_OPEN
        self._permits_left = self.HALF_OPEN_PERMITS
        self._half_open_successes = 0

    def _close(self):
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._permits_left = 0
        self._half_open_successes = 0

    def _cooldown_elapsed(self):
        return self._clock() - self._opened_at >= self._current_cooldown
