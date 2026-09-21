"""自适应采样率的控制器：按窗口吞吐，把每秒采样条数往目标上带。

控制器只管采样率怎么变，不碰窗口也不碰决策。采样器每隔一小段时间喂它一次
窗口统计（每秒采样条数、每秒总条数），它给出下一个采样率。

控制律以前馈为主：目标采样率直接等于 target/total_per_sec（再夹到上下限
里），流量涨和落都一步能算出正确档位，不依赖"上一窗实际采到多少"的滞后
反馈，所以峰值过去沉得回来，也不会因为某窗读 0 被一把拍到 1.0 钉死。
每次只朝目标走 gain 比例（线性插值），并留一个死区，吞吐的小幅抖动不
触发调整。线性更新在目标两侧对称，稳态不会系统性偏高或偏低。
"""

import threading
import time


class RateController:
    """把每秒采样条数维持在 target_per_sec 附近的采样率调节器。

    target_per_sec: 期望的每秒采样条数，流量的账按这个数买。
    min_rate / max_rate: 采样率的上下限，取值都在 (0, 1] 里。
    gain: 每次调整朝目标靠拢的比例，(0, 1]，越小越稳、越慢。
    deadband: 与目标的相对差距在这个比例以内就不动，压住小幅抖动。
    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic。
    """

    def __init__(self, target_per_sec, min_rate=0.001, max_rate=1.0,
                 gain=0.5, deadband=0.0, clock=time.monotonic):
        if target_per_sec <= 0:
            raise ValueError("target_per_sec must be > 0")
        if not 0 < min_rate <= max_rate <= 1.0:
            raise ValueError("rate bounds must be within (0, 1]")
        if not 0 < gain <= 1:
            raise ValueError("gain must be within (0, 1]")
        if not 0 <= deadband < 1:
            raise ValueError("deadband must be within [0, 1)")
        self._target = float(target_per_sec)
        self._min_rate = float(min_rate)
        self._max_rate = float(max_rate)
        self._gain = float(gain)
        self._deadband = float(deadband)
        self._clock = clock
        self._lock = threading.Lock()
        self._rate = float(max_rate)
        self._updates = 0

    @property
    def target_per_sec(self):
        return self._target

    def rate(self):
        """当前生效的采样率。"""
        return self._rate

    def updates(self):
        """已经调整过多少次，排查时看它。"""
        return self._updates

    def observe(self, sampled_per_sec, total_per_sec):
        """拿最近一个窗口的统计推进一步，返回调整后的采样率。

        采样量本身只用来做健全性校验，档位主要由总吞吐前馈算出：这样流量
        回落时升档和流量上涨时降档走同一条对称的路径。
        """
        with self._lock:
            if total_per_sec <= 0:
                # 窗口里没有流量，保持现状，等下一拍有数据再说
                return self._rate
            desired = self._target / total_per_sec
            if desired > self._max_rate:
                desired = self._max_rate
            if desired < self._min_rate:
                desired = self._min_rate
            relative_gap = abs(desired - self._rate) / self._rate
            if relative_gap <= self._deadband:
                # 已经贴在目标档位附近，吞吐的小幅抖动不跟着折腾
                return self._rate
            # 线性插值：朝目标档位走 gain 比例，两侧对称、稳态无偏
            new_rate = self._rate + (desired - self._rate) * self._gain
            if new_rate > self._max_rate:
                new_rate = self._max_rate
            if new_rate < self._min_rate:
                new_rate = self._min_rate
            self._rate = new_rate
            self._updates += 1
            return self._rate

    def reset(self):
        """回到初始档位，模式重新切入自适应时用。"""
        with self._lock:
            self._rate = self._max_rate
            self._updates = 0
