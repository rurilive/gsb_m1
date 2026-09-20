"""重试执行核心。2018 年给任务队列写的兜底层。

重构后只有一个执行循环：retry() 做参数校验并把 strategy 名字换成
策略对象，_run() 负责跑循环。等待时长、用时钟全部交给策略对象
（见 strategies.py），sleep 和时钟可注入，默认行为不变。
行为以 tests/test_backoff.py 为准。
"""

import time

from retrykit.strategies import make_strategy


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


def _run(fn, attempts, strategy, timeout, retry_on, on_retry,
         sleep=None, now=None):
    """单一重试执行循环。sleep/now 可注入，None 时用真实时钟。"""
    if sleep is None:
        sleep = time.sleep
    if now is None:
        now = strategy.now
    started = now()
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as e:
            if attempt >= attempts:
                raise RetryError(
                    "gave up after %d attempts, last error: %r" % (attempt, e))
            if timeout is not None and now() - started >= timeout:
                raise RetryError(
                    "budget of %.2fs exceeded after %d attempts, last error: %r"
                    % (timeout, attempt, e))
            wait = strategy.wait(attempt)
            if on_retry is not None:
                on_retry(attempt, e, wait)
            sleep(wait)


def retry(fn, attempts=3, strategy="fixed", delay=1.0, max_delay=None,
          timeout=None, retry_on=(Exception,), on_retry=None):
    """执行 fn，最多 attempts 次（含首次），失败按 strategy 等待后重试。

    - strategy: "fixed" 固定间隔 / "expo" 指数退避 / "jitter" 全抖动
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
    strat = make_strategy(strategy, delay, max_delay)
    return _run(fn, attempts, strat, timeout, retry_on, on_retry)
