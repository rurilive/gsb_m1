"""链路追踪采样器：按 trace 决定整条调用链采不采。

静态模式按固定比例采样；自适应模式看窗口吞吐动态调采样率，把每秒采样条数
往 target_per_sec 上带。两种模式都只认 trace_id，同一个 trace 的多个 span
应该拿到同一个结论。
"""

import random
import threading
import time
import zlib

from .controller import RateController
from .window import SlidingWindow

MODE_STATIC = "static"
MODE_ADAPTIVE = "adaptive"
MODES = (MODE_STATIC, MODE_ADAPTIVE)

TOTAL_KEY = "total"
SAMPLED_KEY = "sampled"

# 统计窗口切成几格：窗口 1 秒时半秒滚一格
_BUCKETS = 2
# 控制点间隔：取窗口的三分之一，免得每个 span 都去改采样率
_CONTROL_DIVISOR = 3


def trace_unit(trace_id):
    """把 trace_id 落到 [0, 1) 上的一个稳定小数。

    走 crc32，不走内置 hash，同一个 trace_id 换进程、换机器都是同一个值。
    """
    digest = zlib.crc32(str(trace_id).encode("utf-8"))
    return digest / 0x100000000


class TraceSampler:
    """trace 级采样器，进程内共用一份实例。

    rate: 静态模式的采样比例，0 < rate <= 1。
    mode: "static" 固定比例，"adaptive" 按吞吐自适应。
    target_per_sec: 自适应模式下期望的每秒采样条数。
    window_seconds: 统计吞吐用的窗口长度，窗口内部按固定的桶格滚动统计。
    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic。
    """

    def __init__(self, rate=0.1, mode=MODE_STATIC, target_per_sec=100.0,
                 window_seconds=1.0, clock=time.monotonic):
        if not 0 < rate <= 1:
            raise ValueError("rate must be within (0, 1]")
        if mode not in MODES:
            raise ValueError("unknown mode: %r" % (mode,))
        if target_per_sec <= 0:
            raise ValueError("target_per_sec must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._rate = float(rate)
        self._mode = mode
        self._target_per_sec = float(target_per_sec)
        self._window_seconds = float(window_seconds)
        self._control_seconds = self._window_seconds / _CONTROL_DIVISOR
        self._clock = clock
        self._window = SlidingWindow(window_seconds, _BUCKETS, clock)
        self._controller = RateController(target_per_sec, clock=clock)
        self._rng = random.Random()
        self._lock = threading.Lock()
        self._last_control = clock()
        self._total = 0
        self._sampled = 0

    # ---- 对外接口 ----

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        """切换采样模式，静态比例和自适应的账各算各的。"""
        if mode not in MODES:
            raise ValueError("unknown mode: %r" % (mode,))
        with self._lock:
            self._mode = mode

    def rate(self):
        """当前生效的采样率。"""
        if self._mode == MODE_STATIC:
            return self._rate
        return self._controller.rate()

    def should_sample(self, trace_id):
        """这条 trace 的 span 要不要采。"""
        if self._mode == MODE_STATIC:
            return self._static_decision(trace_id)
        return self._adaptive_decision(trace_id)

    def stats(self):
        """当前状态快照，监控面板直接读它。"""
        with self._lock:
            mode = self._mode
            total = self._total
            sampled = self._sampled
        return {
            "mode": mode,
            "rate": self.rate(),
            "target_per_sec": self._target_per_sec,
            "total": total,
            "sampled": sampled,
            "dropped": total - sampled,
            "window_total": self._window.count(TOTAL_KEY),
            "window_sampled": self._window.count(SAMPLED_KEY),
            "updates": self._controller.updates(),
        }

    # ---- 内部实现 ----

    def _static_decision(self, trace_id):
        """固定比例：拿 trace_id 的稳定小数跟比例比大小。"""
        keep = trace_unit(trace_id) < self._rate
        with self._lock:
            self._total += 1
            if keep:
                self._sampled += 1
        return keep

    def _adaptive_decision(self, trace_id):
        """自适应：按当前采样率决定，采到的进窗口的 sampled 账。"""
        with self._lock:
            self._total += 1
        self._window.add(TOTAL_KEY)
        keep = self._rng.random() < self._controller.rate()
        if keep:
            with self._lock:
                self._sampled += 1
            self._window.add(SAMPLED_KEY)
        now = self._clock()
        if now - self._last_control >= self._control_seconds:
            self._last_control = now
            self._step()
        return keep

    def _step(self):
        """把最近一窗的统计喂给控制器。"""
        sampled = self._window.per_second(SAMPLED_KEY)
        total = self._window.per_second(TOTAL_KEY)
        self._controller.observe(sampled, total)
