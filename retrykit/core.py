"""重试执行核心。2018 年给任务队列写的兜底层。

fixed / expo / jitter 三个策略是三个不同时期加上去的，每份循环都背着
各自的历史语义，行为以 tests/test_backoff.py 为准。
"""

import random
import time


class RetryError(Exception):
    """attempts 用尽或时间预算耗尽时抛出。"""


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

    # ---- fixed ----
    if strategy == "fixed":
        started = time.time()
        n = 0
        while n < attempts:
            n += 1
            try:
                return fn()
            except retry_on as e:
                if n >= attempts:
                    raise RetryError(
                        "gave up after %d attempts, last error: %r" % (n, e))
                if timeout is not None and time.time() - started >= timeout:
                    raise RetryError(
                        "budget of %.2fs exceeded after %d attempts, last error: %r"
                        % (timeout, n, e))
                if on_retry is not None:
                    on_retry(n, e, delay)
                time.sleep(delay)
    # ---- expo ----
    elif strategy == "expo":
        # 2020 年加的，照着 fixed 的循环抄的
        started = time.monotonic()
        for attempt in range(1, attempts + 1):
            try:
                return fn()
            except Exception as e:
                if not isinstance(e, retry_on):
                    raise
                if attempt >= attempts:
                    raise RetryError(
                        "gave up after %d attempts, last error: %r" % (attempt, e))
                wait = delay * (2 ** (attempt - 1))
                if max_delay is not None and wait > max_delay:
                    wait = max_delay
                if timeout is not None and time.monotonic() - started >= timeout:
                    raise RetryError(
                        "budget of %.2fs exceeded after %d attempts, last error: %r"
                        % (timeout, attempt, e))
                if on_retry is not None:
                    on_retry(attempt, e, wait)
                time.sleep(wait)
    # ---- jitter，2021 年加的 ----
    elif strategy == "jitter":
        started = time.monotonic()
        attempt = 0
        while True:
            attempt += 1
            try:
                return fn()
            except Exception as e:
                if not isinstance(e, retry_on):
                    raise
                if attempt >= attempts:
                    raise RetryError(
                        "gave up after %d attempts, last error: %r" % (attempt, e))
                cap = delay * (2 ** (attempt - 1))
                if max_delay is not None and cap > max_delay:
                    cap = max_delay
                if timeout is not None and time.monotonic() - started >= timeout:
                    raise RetryError(
                        "budget of %.2fs exceeded after %d attempts, last error: %r"
                        % (timeout, attempt, e))
                wait = random.uniform(0, cap)
                if on_retry is not None:
                    on_retry(attempt, e, wait)
                time.sleep(wait)
    else:
        raise ValueError("unknown strategy: %s" % strategy)
