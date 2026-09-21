"""自适应采样率的控制器：按窗口吞吐，把每秒采样条数往目标上带。

控制器只管采样率怎么变，不碰窗口也不碰决策。采样器每隔一小段时间喂它一次
窗口统计（每秒总条数为主，每秒采样条数仅用于对账），它给出下一个采样率。

调节方式：

- 期望采样率 = min(1, target / total)。流量高于目标时按比例采，低于目标时
  全采（上限 1.0）。直接拿总吞吐算，而不是拿采样结果反推，避免 sampled 和
  total 两个计数读岔时把阈值一步拽到地板。
- 对期望率做指数平滑（EMA），流量的小幅抖动不会让采样率一惊一乍。
- 死区：期望率和当前率相差很小时按兵不动，稳态不抖动。
- 限幅：单步变化封顶一个倍数，读数学到尖刺也不会一步砸到 min_rate。
- 第一步（或 reset 后）直接对齐期望率，不做平滑，冷启动不超采。

控制器自身线程安全：rate() 无锁读（只是取一个 float），observe/reset 加锁。
"""

import threading
import time

# EMA 平滑系数：越大跟得越快，越小越稳
_EMA_ALPHA = 0.6
# 死区：期望率跟当前率的相对偏差不到这个比例就不动，压住小波动
_DEADBAND = 0.05
# 单步变化最多翻/砍多少倍，防脏读数一步带飞
_MAX_STEP_FACTOR = 10.0


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
        self._primed = False
        self._lock = threading.Lock()

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
        """回到初始状态（上限采样率、平滑从头来）。"""
        with self._lock:
            self._rate = self._max_rate
            self._updates = 0
            self._primed = False

    def observe(self, sampled_per_sec, total_per_sec):
        """拿最近一个窗口的统计推进一步，返回调整后的采样率。

        决策只看 total_per_sec；sampled_per_sec 留作对账，不再参与阈值
        计算，因此两个计数瞬时读岔不会把采样率拽飞。
        """
        with self._lock:
            if total_per_sec <= 0:
                # 窗口里没有流量，维持现状，等流量回来再说
                return self._rate
            desired = self._target / total_per_sec
            if desired >= self._max_rate:
                # 流量低于目标：全采，直接顶到上限，不拖平滑
                target_rate = self._max_rate
            elif abs(desired - self._rate) < self._rate * _DEADBAND:
                # 期望值就在当前率附近（小幅流量抖动），按兵不动。
                # 必须拿期望值而不是平滑后的候选值跟当前率比：否则候选值
                # 每步都落进死区，EMA 只会渐近、永远够不着真正的目标。
                target_rate = self._rate
            elif not self._primed:
                # 冷启动第一拍直接对齐，避免按 1.0 超采一整段
                target_rate = max(self._min_rate, min(self._max_rate, desired))
            else:
                smoothed = self._rate + _EMA_ALPHA * (desired - self._rate)
                lower = max(self._min_rate, self._rate / _MAX_STEP_FACTOR)
                upper = min(self._max_rate, self._rate * _MAX_STEP_FACTOR)
                target_rate = min(max(smoothed, lower), upper)
                target_rate = max(self._min_rate,
                                  min(self._max_rate, target_rate))
            if target_rate != self._rate:
                self._rate = target_rate
            self._updates += 1
            self._primed = True
            return self._rate
