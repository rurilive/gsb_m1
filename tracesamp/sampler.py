"""链路追踪采样器：按 trace 决定整条调用链采不采。

静态模式按固定比例采样；自适应模式看窗口吞吐动态调采样率，把每秒采样条数
往 target_per_sec 上带。两种模式都只认 trace_id，同一个 trace 的多个 span
应该拿到同一个结论。
"""

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
# 决策缓存：一条 trace 的结论至少保留这么久，跨度几秒的 span 才拿得到
# 同一个答案；同时给缓存设上限，极端流量下内存也有顶
_DECISION_TTL_MIN = 10.0
_DECISION_TTL_WINDOWS = 5
_DECISION_CACHE_MAX = 200000
_DECISION_PRUNE_INTERVAL = 1.0


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
        self._lock = threading.Lock()
        self._control_lock = threading.Lock()
        self._decision_lock = threading.Lock()
        self._decisions = {}
        self._decision_ttl = max(_DECISION_TTL_MIN,
                                 _DECISION_TTL_WINDOWS * self._window_seconds)
        self._last_control = clock()
        self._last_prune = self._last_control
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
        window = self._window.counts((TOTAL_KEY, SAMPLED_KEY))
        return {
            "mode": mode,
            "rate": self.rate(),
            "target_per_sec": self._target_per_sec,
            "total": total,
            "sampled": sampled,
            "dropped": total - sampled,
            "window_total": window[TOTAL_KEY],
            "window_sampled": window[SAMPLED_KEY],
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
        """自适应：结论按 trace 缓存，同一条 trace 的 span 早晚到都一样。"""
        now = self._clock()
        keep = self._decision_for(trace_id, now)
        with self._lock:
            self._total += 1
            if keep:
                self._sampled += 1
        self._window.add(TOTAL_KEY)
        if keep:
            self._window.add(SAMPLED_KEY)
        self._maybe_control(now)
        return keep

    def _decision_for(self, trace_id, now):
        """拿这条 trace 的自适应结论，缓存里没有就按当前采样率算一条存起来。

        结论由 trace_id 的稳定小数跟采样率比大小得出，跟静态模式同一套
        比法；缓存把结论钉住，采样率随后怎么调都不影响已经在路上的 span。
        """
        with self._decision_lock:
            entry = self._decisions.get(trace_id)
            if entry is not None and entry[1] > now:
                return entry[0]
            keep = trace_unit(trace_id) < self._controller.rate()
            self._decisions[trace_id] = (keep, now + self._decision_ttl)
            if (len(self._decisions) > _DECISION_CACHE_MAX
                    and now - self._last_prune >= _DECISION_PRUNE_INTERVAL):
                self._last_prune = now
                self._prune_decisions(now)
            return keep

    def _prune_decisions(self, now):
        """先清过期项，还超上限就按写入先后挤掉最旧的。调用方已持锁。"""
        expired = [tid for tid, (_, deadline) in self._decisions.items()
                   if deadline <= now]
        for tid in expired:
            del self._decisions[tid]
        overflow = len(self._decisions) - _DECISION_CACHE_MAX
        if overflow > 0:
            for tid in list(self._decisions)[:overflow]:
                del self._decisions[tid]

    def _maybe_control(self, now):
        """到控制点了就把最近一窗的统计喂给控制器，多线程只放一路进去。"""
        if now - self._last_control < self._control_seconds:
            return
        with self._control_lock:
            now = self._clock()
            if now - self._last_control < self._control_seconds:
                return
            self._last_control = now
            window, covered = self._window.readings((SAMPLED_KEY, TOTAL_KEY))
            self._controller.observe(
                window[SAMPLED_KEY] / covered,
                window[TOTAL_KEY] / covered)
