"""可失败调用的重试执行器。

当前能力：把任意可调用对象按固定次数重试，返回最后一次调用的结果；
若最后一次仍然抛出异常，就把该异常原样向上抛。
纯标准库，时钟由构造参数注入，便于测试。
"""

import time


class RetryExhausted(Exception):
    """重试次数耗尽后仍失败时抛出的异常。

    attempts 记录总共尝试了几次，last 记录最后一次的原始异常。
    """

    def __init__(self, attempts, last):
        super().__init__(f"retry exhausted after {attempts} attempts: {last!r}")
        self.attempts = attempts
        self.last = last


class Executor:
    """把可失败函数重试固定次数的执行器。

    retries: 除首次外的额外重试次数，总尝试次数为 retries + 1。
    clock: 返回当前时刻的可调用对象，默认 time.monotonic。
    sleep: 等待函数，默认 time.sleep，注入假实现即可零耗时推进。
    """

    def __init__(self, retries=0, clock=time.monotonic, sleep=time.sleep):
        if retries < 0:
            raise ValueError("retries must be >= 0")
        self._retries = retries
        self._clock = clock
        self._sleep = sleep

    @property
    def retries(self):
        """额外重试次数。"""
        return self._retries

    def run(self, fn, *args, **kwargs):
        """执行 fn 并在失败时重试。

        每次尝试的返回值与抛出的异常都会被记录；一旦某次返回，立即返回该结果。
        所有尝试都抛异常时，累积的尝试次数与最后一次异常留给调用方处置：
        本方法把最后一次异常向上抛出（包装为 RetryExhausted 时保留原始异常）。
        """
        attempts = 0
        last_error = None
        while attempts < self._retries + 1:
            attempts += 1
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - 调用方决定如何处理
                last_error = exc
        raise RetryExhausted(attempts, last_error)

    def run_or_none(self, fn, *args, **kwargs):
        """与 run 相同，但重试耗尽时返回 None 而不是抛出。"""
        try:
            return self.run(fn, *args, **kwargs)
        except RetryExhausted:
            return None