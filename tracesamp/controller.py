"""自适应采样率的控制器：按窗口统计，把每秒采样条数往目标上带。

控制器只管采样率怎么变，不碰窗口也不碰决策。采样器每隔一小段时间喂它一次
窗口统计（每秒采样条数、每秒总条数），它给出下一个采样率。
"""

import threading
import time

# 死区：每秒采样条数在目标上下 10% 以内就不动，流量小幅波动不跟着晃
_DEADBAND = 0.10
# 单步调整幅度上限：一次最多翻一倍、最多砍一半，峰谷都分几步靠过去，
# 免得一个窗口的读数把采样率一步拽到地板上
_MAX_STEP_UP = 2.0
_MAX_STEP_DOWN = 0.5


class RateController:
    """把每秒采样条数维持在 target_per_sec 附近的采样率调节器。

    target_per_sec: 期望的每秒采样条数，流量的账按这个数买。
    min_rate / max_rate: 采样率的上下限，取值都在 (0, 1] 里。
    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic。
    """

    def __init__(self, target_per_sec, min_rate=0.001, max_rate=1.0,
                 clock=time.monotonic):
        if target_per_sec <= 0:
            raise ValueError("target_per_sec must be > 0")
        if not 0 < min_rate <= max_rate <= 1.0:
            raise ValueError("rate bounds must be within (0, 1]")
        self._target = float(target_per_sec)
        self._min_rate = float(min_rate)
        self._max_rate = float(max_rate)
        self._clock = clock
        self._lock = threading.Lock()
        self._rate = float(max_rate)
        self._updates = 0

    @property
    def target_per_sec(self):
        return self._target

    def rate(self):
        """当前生效的采样率。"""
        with self._lock:
            return self._rate

    def updates(self):
        """已经调整过多少次，排查时看它。"""
        with self._lock:
            return self._updates

    def observe(self, sampled_per_sec, total_per_sec):
        """拿最近一个窗口的统计推进一步，返回调整后的采样率。"""
        with self._lock:
            if total_per_sec <= 0:
                # 窗口里没有流量，没什么可调的
                return self._rate
            # 这一窗的总吞吐下，要贴住目标该有的采样率
            desired = self._target / total_per_sec
            desired = min(max(desired, self._min_rate), self._max_rate)
            lower = self._target * (1.0 - _DEADBAND)
            upper = self._target * (1.0 + _DEADBAND)
            rate = self._rate
            if sampled_per_sec > upper and rate > desired:
                # 采超了，往 desired 压，一步最多砍一半
                rate = max(desired, rate * _MAX_STEP_DOWN)
            elif sampled_per_sec < lower and rate < desired:
                # 采少了（包括峰值过去流量回落），往 desired 抬，一步最多翻一倍
                rate = min(desired, rate * _MAX_STEP_UP)
            if rate != self._rate:
                self._rate = rate
                self._updates += 1
            return self._rate
