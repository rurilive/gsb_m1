"""重试执行核心。2018 年给任务队列写的兜底层。

fixed / expo / jitter 已收敛为同一个执行循环 + 策略对象
（见 retrykit/strategies.py）。本模块只负责：尝试执行、异常判定、
时间预算、回调时序，等待曲线完全交给策略。行为以
tests/test_backoff.py 为准。
"""

import time

from retrykit.strategies import (
    Backoff,
    CallableBackoff,
    ExpoBackoff,
    FixedBackoff,
    JitterBackoff,
)


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


_STRATEGIES = {
    "fixed": FixedBackoff,
    "expo": ExpoBackoff,
    "jitter": JitterBackoff,
}


def _resolve_strategy(strategy, delay, max_delay):
    """把 strategy 参数解析成 Backoff 实例。

    - 内置名字 "fixed"/"expo"/"jitter"；其他字符串抛 ValueError
    - Backoff 实例原样使用
    - 可调用对象按 attempt -> seconds 的自定义曲线适配
    """
    if isinstance(strategy, Backoff):
        return strategy
    if callable(strategy):
        return CallableBackoff(strategy)
    try:
        cls = _STRATEGIES[strategy]
    except KeyError:
        raise ValueError("unknown strategy: %s" % strategy)
    return cls(delay, max_delay)


class RetryExecutor(object):
    """单一重试循环。sleep / 时钟可注入，默认与线上行为一致。"""

    def __init__(self, sleep=None, clock=None):
        # 延迟到 run 时再取默认值，保证外部对 time.sleep /
        # time.monotonic 的打补丁依然生效。
        self._sleep = sleep
        self._clock = clock

    def run(self, fn, attempts, backoff, timeout, retry_on, on_retry):
        sleep = self._sleep if self._sleep is not None else time.sleep
        now = self._clock if self._clock is not None else time.monotonic

        started = now()
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as e:
                if not isinstance(e, retry_on):
                    raise
                if attempt >= attempts:
                    raise RetryError(
                        "gave up after %d attempts, last error: %r" % (attempt, e))
                backoff.prepare(attempt)
                if timeout is not None and now() - started >= timeout:
                    raise RetryError(
                        "budget of %.2fs exceeded after %d attempts, last error: %r"
                        % (timeout, attempt, e))
                wait = backoff.wait(attempt)
                if on_retry is not None:
                    on_retry(attempt, e, wait)
                sleep(wait)


def retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None,
          timeout=None, retry_on=(Exception,), on_retry=None):
    """执行 fn，最多 attempts 次（含首次），失败按 strategy 等待后重试。

    - strategy: "fixed" 固定间隔 / "expo" 指数退避 / "jitter" 全抖动；
      也可传 Backoff 实例，或 attempt -> seconds 的可调用对象作为
      自定义退避曲线
    - delay: 基础等待秒数；expo/jitter 第 n 次失败后的上限是 delay * 2**(n-1)
    - max_delay: expo/jitter 单次等待上限，None 表示不设上限
    - timeout: 整个调用的时间预算（秒），某次失败后已超预算则立刻放弃，
      与重试耗尽抛的 RetryError 文本不同
    - retry_on: 可重试异常类元组，不在里面的异常原样抛出
    - on_retry(attempt, exc, wait): 即将重试前回调，attempt 从 1 计，
      最后一次失败不回调
    - 成功时原样返回 fn 的返回值（falsy 也算成功），放弃时抛 RetryError
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    backoff = _resolve_strategy(strategy, delay, max_delay)
    return RetryExecutor().run(
        fn, attempts, backoff, timeout, retry_on, on_retry)
