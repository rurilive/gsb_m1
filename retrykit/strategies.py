"""退避策略层：只管"第 attempt 次失败后等多久"，不参与重试循环。

策略分两阶段供循环调用：
1. prepare(attempt) 做随机抽样之类的副作用（jitter 用）；
2. wait(attempt) 返回最终等待秒数。

自定义退避曲线只需实现 wait(attempt)（或直接传一个
``attempt -> seconds`` 的可调用对象给 retry），循环、预算、回调
判断都不用动。
"""

import random


class Backoff(object):
    """策略基类。等待序列 = delay * 2 ** (attempt - 1)。"""

    def __init__(self, delay, max_delay=None):
        self.delay = delay
        self.max_delay = max_delay

    def prepare(self, attempt):
        """循环在时间预算检查之前调用；默认无副作用。"""
        pass

    def _cap(self, seconds):
        if self.max_delay is not None and seconds > self.max_delay:
            return self.max_delay
        return seconds

    def wait(self, attempt):
        """返回第 attempt 次失败（attempt 从 1 计）后的等待秒数。"""
        raise NotImplementedError


class FixedBackoff(Backoff):
    """固定间隔。历史上 fixed 不认 max_delay，保持该语义。"""

    def wait(self, attempt):
        return self.delay


class ExpoBackoff(Backoff):
    """指数退避：delay * 2 ** (attempt - 1)，受 max_delay 封顶。"""

    def wait(self, attempt):
        return self._cap(self.delay * (2 ** (attempt - 1)))


class JitterBackoff(Backoff):
    """全抖动：在 [0, expo 同次上限] 内均匀抽样。"""

    def __init__(self, delay, max_delay=None, rng=None):
        super(JitterBackoff, self).__init__(delay, max_delay)
        self._rng = rng
        self._drawn = 0.0

    def prepare(self, attempt):
        uniform = random.uniform if self._rng is None else self._rng
        self._drawn = uniform(0, self._cap(self.delay * (2 ** (attempt - 1))))

    def wait(self, attempt):
        return self._drawn


class CallableBackoff(Backoff):
    """把 ``attempt -> seconds`` 可调用对象适配成策略对象。"""

    def __init__(self, curve):
        super(CallableBackoff, self).__init__(delay=0)
        self._curve = curve

    def wait(self, attempt):
        return self._curve(attempt)
