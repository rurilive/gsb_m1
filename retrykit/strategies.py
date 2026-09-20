"""退避策略层：每个策略对象只回答一个问题——第 n 次失败后等多久。

策略接口（非正式协议）：
- wait(attempt): 第 attempt 次失败（从 1 计）后、重试前的等待秒数
- now(): 该策略做时间预算判断时用的时钟（历史原因 fixed 用 wall
  clock，expo/jitter 用 monotonic，行为以 tests/test_backoff.py 为准）

要接自定义退避曲线，只要提供同样两个方法的对象（或用
CallableStrategy 包一个普通函数），执行循环不需要任何改动。
"""

import random
import time


class FixedStrategy(object):
    """固定间隔：每次失败后都等 delay 秒。"""

    def __init__(self, delay, max_delay=None):
        self._delay = delay

    def now(self):
        return time.time()

    def wait(self, attempt):
        return self._delay


class ExpoStrategy(object):
    """指数退避：第 n 次失败后等 delay * 2**(n-1)，可选 max_delay 封顶。"""

    def __init__(self, delay, max_delay=None):
        self._delay = delay
        self._max_delay = max_delay

    def now(self):
        return time.monotonic()

    def wait(self, attempt):
        wait = self._delay * (2 ** (attempt - 1))
        if self._max_delay is not None and wait > self._max_delay:
            wait = self._max_delay
        return wait


class JitterStrategy(ExpoStrategy):
    """全抖动：在 [0, 同 expo 的上限] 内均匀取值。"""

    def wait(self, attempt):
        return random.uniform(0, super().wait(attempt))


class CallableStrategy(object):
    """把调用方传入的退避曲线函数 wait(attempt) 适配成策略对象。"""

    def __init__(self, curve):
        self._curve = curve

    def now(self):
        return time.monotonic()

    def wait(self, attempt):
        return self._curve(attempt)


_REGISTRY = {
    "fixed": FixedStrategy,
    "expo": ExpoStrategy,
    "jitter": JitterStrategy,
}


def make_strategy(name, delay, max_delay):
    """按名字构造内置策略；名字不认识时抛 ValueError。"""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ValueError("unknown strategy: %s" % name)
    return cls(delay, max_delay)
