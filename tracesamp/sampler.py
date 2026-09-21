"""链路追踪采样器：按 trace 决定整条调用链采不采。

静态模式按固定比例采样；自适应模式看窗口吞吐动态调采样率，把每秒采样条数
往 target_per_sec 上带。两种模式都只认 trace_id，同一个 trace 的多个 span
拿到同一个结论。

自适应模式下采样率会随时间变，光靠 trace_unit(trace_id) < rate 无法保证
同一条 trace 的结论一致（rate 一变结论就可能翻转）。因此自适应路径维护了
一份按 trace_id 钉结论的决策缓存：一条 trace 第一次出现时按当时的采样率
确定性地拍板，之后它所有的 span（隔几秒才到齐或几十个同时挤进）都复用同一
个结论。缓存按 trace_id 哈希分片，每片带 TTL + LRU 淘汰，内存有界且热路径
不被一把全局锁打死。

决策（怎么拍板、缓存怎么钉）与统计（窗口怎么记账、阈值怎么调）完全分开：
should_sample 只做决策和记账，阈值由 RateController 在独立的控制步上依据
SlidingWindow 的一致性快照推进。
"""

import threading
import time
import zlib
from collections import OrderedDict

from .controller import RateController
from .window import SlidingWindow

MODE_STATIC = "static"
MODE_ADAPTIVE = "adaptive"
MODES = (MODE_STATIC, MODE_ADAPTIVE)

TOTAL_KEY = "total"
SAMPLED_KEY = "sampled"

# 统计窗口切成几格：窗口 1 秒时半秒滚一格
_BUCKETS = 2
# 控制点间隔：窗口的四分之一，既不每个 span 都动阈值，又能快速收敛
_CONTROL_DIVISOR = 4
# 启动后多快走第一步控制：抢在按 1.0 超采一整秒之前把阈值带上
_FIRST_CONTROL_SECONDS = 0.05
# 决策缓存分片数：打散热点，避免一把大锁
_DECISION_SHARDS = 32
# 每片缓存多少条 trace 的结论
_DECISION_SHARD_CAPACITY = 4096
# 一条 trace 的结论钉多久：覆盖同一条 trace span 的正常到齐时间
_DECISION_TTL_SECONDS = 8.0


def trace_unit(trace_id):
    """把 trace_id 落到 [0, 1) 上的一个稳定小数。

    走 crc32，不走内置 hash，同一个 trace_id 换进程、换机器都是同一个值。
    """
    digest = zlib.crc32(str(trace_id).encode("utf-8"))
    return digest / 0x100000000


class _DecisionCache:
    """按 trace_id 钉采样结论的分片缓存。

    每片是一条按插入顺序排列的 OrderedDict：trace_id -> (结论, 到期时刻)。
    淘汰策略刻意做成摊销 O(1)：容量没满就直接进；满了就从队首弹，队首已
    过期算惰性清理、没过期算 FIFO。绝不周期性整队扫描——十几万个条目时
    一次全表清扫就能把热路径卡出一个坑。分片之间各有各的锁，多个线程问
    不同的 trace 互不排队。
    """

    def __init__(self, clock, shards=_DECISION_SHARDS,
                 capacity=_DECISION_SHARD_CAPACITY,
                 ttl_seconds=_DECISION_TTL_SECONDS):
        self._clock = clock
        self._shards = shards
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._locks = [threading.Lock() for _ in range(shards)]
        self._entries = [OrderedDict() for _ in range(shards)]

    def get_or_decide(self, trace_id, rate):
        """返回这条 trace 的结论；没有旧账时按 rate 现拍并钉住。"""
        key = str(trace_id)
        shard_index = (zlib.crc32(key.encode("utf-8")) & 0x7FFFFFFF) % self._shards
        entries = self._entries[shard_index]
        now = self._clock()
        with self._locks[shard_index]:
            hit = entries.get(key)
            if hit is not None and hit[1] >= now:
                # 命中只续期，不挪位置（挪动会让长命 trace 永不老化）
                entries[key] = (hit[0], now + self._ttl)
                return hit[0]
            keep = trace_unit(key) < rate
            entries[key] = (keep, now + self._ttl)
            if len(entries) > self._capacity:
                # 只从队首弹：先连着掉过期的，再 FIFO 掉最老的直到不溢出
                while len(entries) > self._capacity:
                    entries.popitem(last=False)
            return keep

    def clear(self):
        """全部结论作废（模式重置时用）。"""
        for shard_index in range(self._shards):
            with self._locks[shard_index]:
                self._entries[shard_index].clear()


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
        self._counter_lock = threading.Lock()
        self._control_lock = threading.Lock()
        self._decisions = _DecisionCache(clock)
        self._last_control = clock() - self._control_seconds + _FIRST_CONTROL_SECONDS
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
            if mode == MODE_ADAPTIVE and self._mode != MODE_ADAPTIVE:
                # 重新进入自适应：窗口、阈值、钉过的结论全部从头来
                self._window.reset()
                self._controller.reset()
                self._decisions.clear()
                self._last_control = (
                    self._clock() - self._control_seconds + _FIRST_CONTROL_SECONDS)
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
        with self._counter_lock:
            total = self._total
            sampled = self._sampled
        window_counts = self._window.snapshot((TOTAL_KEY, SAMPLED_KEY))
        return {
            "mode": mode,
            "rate": self.rate(),
            "target_per_sec": self._target_per_sec,
            "total": total,
            "sampled": sampled,
            "dropped": total - sampled,
            "window_total": window_counts[TOTAL_KEY],
            "window_sampled": window_counts[SAMPLED_KEY],
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
        """自适应：按 trace 拍板（结论钉在缓存里），账原子地进窗口。"""
        keep = self._decisions.get_or_decide(trace_id, self._controller.rate())
        now = self._clock()
        self._window.add_many(
            ((TOTAL_KEY, 1), (SAMPLED_KEY, 1)) if keep
            else ((TOTAL_KEY, 1),))
        with self._counter_lock:
            self._total += 1
            if keep:
                self._sampled += 1
        if now - self._last_control >= self._control_seconds:
            # 控制步另走一把锁，抢锁失败说明别的线程已经调过，别堵住决策
            if self._control_lock.acquire(blocking=False):
                try:
                    if now - self._last_control >= self._control_seconds:
                        self._last_control = now
                        self._step()
                finally:
                    self._control_lock.release()
        return keep

    def _step(self):
        """把最近一窗的统计（同一批桶的快照）喂给控制器。"""
        rates = self._window.rates((SAMPLED_KEY, TOTAL_KEY))
        sampled = rates[SAMPLED_KEY]
        total = rates[TOTAL_KEY]
        self._controller.observe(sampled, total)
