"""自适应采样率的控制器：按窗口吞吐直接算出该用多大的采样率。

控制器只回答一个问题：以最近的吞吐，采多少比例才能刚好贴住目标。它不碰
窗口、不碰决策，采样器定时把每秒总条数（吞吐）和每秒采样条数喂给它，
它返回下一个采样率。

调节方式：

- 吞吐做指数滑动平均（EMA），窗口里的一格抖动只被吸收一部分，不会
  因为一两个尖刺就把采样率甩出去；
- 采样率直接按 ``target / 平滑吞吐`` 反演，流量翻倍采样率就减半，
  不存在“乘法往下砍、靠极端值往回升”的来回抽风；
- 每步变动夹在 [1/4, 4] 倍之内（首次观测除外），即使窗口读数异常
  也不会一步钉到地板或天花板；
- 窗口里没有流量时保持原采样率，恢复流量后由后续观测平滑带回来，
  不再有“一条没采到就拽到 1.0”的动作。
"""

import time

# 吞吐 EMA 系数：每次观测采信 2/3 新值、保留 1/3 历史。窗口 1 秒、
# 控制间隔 1/4 秒时，约一秒钟的历史参与平滑，小波动不敏感，峰值
# 过后两三步就能沉回来。
_THROUGHPUT_ALPHA = 2.0 / 3.0

# 单次调整允许的最大倍率，防止异常读数把采样率一步甩飞。
_MAX_STEP_FACTOR = 4.0


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
        self._rate = float(max_rate)
        self._updates = 0
        self._throughput = None

    @property
    def target_per_sec(self):
        return self._target

    def rate(self):
        """当前生效的采样率。"""
        return self._rate

    def updates(self):
        """已经调整过多少次，排查时看它。"""
        return self._updates

    def reset(self):
        """回到初始状态：采样率恢复上限，忘掉平滑历史。"""
        self._rate = float(self._max_rate)
        self._throughput = None
        self._updates = 0

    def observe(self, sampled_per_sec, total_per_sec):
        """拿最近一个窗口的统计推进一步，返回调整后的采样率。

        sampled_per_sec 仅用于观察/诊断，采样率只由吞吐反演：
        吞吐 × 采样率 = 目标采样条数。同一条 trace 的决策恒定，
        这个等式天然成立，不需要再拿 sampled 做反馈闭环。
        """
        if total_per_sec <= 0:
            # 窗口里没有流量，保持现状，等流量回来再算
            return self._rate
        throughput = float(total_per_sec)
        if self._throughput is None:
            self._throughput = throughput
            desired = self._target / throughput
            # 首次观测直接到位，避免起步阶段长时间过量采样
            self._rate = self._clamp(desired)
        else:
            self._throughput += _THROUGHPUT_ALPHA * (throughput
                                                     - self._throughput)
            desired = self._target / self._throughput
            lower = self._rate / _MAX_STEP_FACTOR
            upper = self._rate * _MAX_STEP_FACTOR
            self._rate = self._clamp(min(max(desired, lower), upper))
        self._updates += 1
        return self._rate

    def _clamp(self, value):
        """夹到采样率上下限内。"""
        if value < self._min_rate:
            return self._min_rate
        if value > self._max_rate:
            return self._max_rate
        return value
