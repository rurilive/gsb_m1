"""链路追踪采样器：按 trace 决定整条调用链采不采。

静态模式按固定比例采样；自适应模式看窗口吞吐动态调采样率，把每秒采样条数
往 target_per_sec 上带。两种模式都只认 trace_id，同一个 trace 的多个 span
必须拿到同一个结论。

自适应模式里"决策"和"统计"是两件事：

- 决策按 trace 走：同一条 trace 第一次出现时，用它稳定的 trace_unit 跟当前
  采样率比一次大小，结论记进分片决策缓存；这条 trace 后续的 span（无论隔
  几秒、挤多少并发）都直接复用缓存，不再重新掷骰子。缓存带 TTL 和每片
  容量上限，内存不会被长尾 trace 撑爆。
- 统计只记账：每个 span 在窗口里原子记 total，采到的再原子记 sampled。
  采样器每隔控制间隔从窗口取一次多键原子快照喂给控制器，控制器只调档位，
  不碰任何单条决策。

锁也按职责拆开：计数锁、窗口锁（在 SlidingWindow 内部）、决策缓存分片锁、
控制推进锁各管各的，热路径上没有一把全局大锁串行所有 span。
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

# 统计窗口切成几格：窗口 1 秒时 0.05 秒滚一格。格越细，单格整格进出对
# 窗口读数的冲击越小，控制器看到的吞吐越平稳。
_BUCKETS = 20
# 控制间隔 = 窗口 / 该除数；拍密一点让吞吐反馈更跟手，又不至于每个 span 都调
_CONTROL_DIVISOR = 10
# 决策缓存分片数：按 trace_unit 分片，片内一把小锁，片间完全并行
_DECISION_SHARDS = 32
# 同一条 trace 的决策保留多久：覆盖一条 trace 的 span 正常到齐的时间跨度
_DECISION_TTL = 5.0
# 每片缓存的条目硬上限，防长尾 trace_id 把内存吃光
_DECISION_SHARD_CAP = 16384

# splitmix64 收尾用的雪崩常数：给 crc32 的结果再做一次充分位混合。
# 直接用 crc32 时，连续生成的 trace_id（t-0、t-1、...）在小集合上的落点
# 会成片偏离均匀，导致"配置采样率"和"实际采样比例"对不上；雪崩后小样本
# 上也贴着均匀走。结果仍只由 trace_id 决定，换进程、换机器不变。
_MIX64_MASK = (1 << 64) - 1
_MIX64_GOLDEN = 0x9E3779B97F4A7C15
_MIX64_A = 0xBF58476D1CE4E5B9
_MIX64_B = 0x94D049BB133111EB


def _avalanche64(value):
    """splitmix64 的收尾混合：把 64 位输入打散成近似均匀的 64 位输出。"""
    value = (value + _MIX64_GOLDEN) & _MIX64_MASK
    value = (value ^ (value >> 30)) * _MIX64_A & _MIX64_MASK
    value = (value ^ (value >> 27)) * _MIX64_B & _MIX64_MASK
    return value ^ (value >> 31)


def trace_unit(trace_id):
    """把 trace_id 落到 [0, 1) 上的一个稳定小数。

    先 crc32（不走内置 hash）再做 64 位雪崩混合，同一个 trace_id 换进程、
    换机器都是同一个值，连续命名的 trace_id 在小集合上也近似均匀。
    """
    digest = _avalanche64(zlib.crc32(str(trace_id).encode("utf-8")))
    return digest / (1 << 64)


class _DecisionCache:
    """trace_id -> 首次决策 的分片缓存，带 TTL 与容量上限。

    每个条目记 (结论, 首次见到的时刻)。命中且没过期就复用；过期了按当前
    档位重新判一次（长尾 trace 超过 TTL 才可能前后结论不同，正常调用链
    不受影响）。每片有硬上限，超限时先扫过期条目，还不够就丢最早的条目。
    """

    def __init__(self, shards, ttl_seconds, shard_cap, clock):
        self._ttl = float(ttl_seconds)
        self._cap = int(shard_cap)
        self._clock = clock
        self._shards = [dict() for _ in range(shards)]
        self._locks = [threading.Lock() for _ in range(shards)]

    def decide(self, trace_id, unit, rate, now=None):
        """返回这条 trace 此刻应有的稳定结论（bool）。"""
        shard_index = int(unit * len(self._shards)) % len(self._shards)
        if now is None:
            now = self._clock()
        lock = self._locks[shard_index]
        with lock:
            shard = self._shards[shard_index]
            entry = shard.get(trace_id)
            if entry is not None and now - entry[1] < self._ttl:
                return entry[0]
            keep = unit < rate
            shard[trace_id] = (keep, now)
            if len(shard) > self._cap:
                # 容量兜底只在写爆时才发生：顺手清过期条目，仍超限再丢
                # 最早的一批。正常靠 TTL 惰性过期，没有任何周期性全表扫描。
                self._enforce_cap(shard, now)
            return keep

    def clear(self):
        for shard, lock in zip(self._shards, self._locks):
            with lock:
                shard.clear()

    def _enforce_cap(self, shard, now):
        # 先清过期条目兜底，仍超上限再按首次见到的时间丢最早的。
        stale = [key for key, entry in shard.items()
                 if now - entry[1] >= self._ttl]
        for key in stale:
            del shard[key]
        if len(shard) <= self._cap:
            return
        overflow = len(shard) - self._cap
        # O(n) 挑出最早的 overflow 个删掉，避免对整片排序。
        oldest_keys = list(shard)
        oldest_keys.sort(key=lambda key: shard[key][1])
        for key in oldest_keys[:overflow]:
            del shard[key]


class TraceSampler:
    """trace 级采样器，进程内共用一份实例。

    rate: 静态模式的采样比例，0 < rate <= 1。
    mode: "static" 固定比例，"adaptive" 按吞吐自适应。
    target_per_sec: 自适应模式下期望的每秒采样条数。
    window_seconds: 统计吞吐用的窗口长度，窗口内部按固定的桶格滚动统计。
    decision_ttl: 自适应模式下同一条 trace 的决策保留秒数。
    clock: 返回当前时刻（秒）的可调用对象，默认 time.monotonic。
    """

    def __init__(self, rate=0.1, mode=MODE_STATIC, target_per_sec=100.0,
                 window_seconds=1.0, decision_ttl=_DECISION_TTL,
                 clock=time.monotonic):
        if not 0 < rate <= 1:
            raise ValueError("rate must be within (0, 1]")
        if mode not in MODES:
            raise ValueError("unknown mode: %r" % (mode,))
        if target_per_sec <= 0:
            raise ValueError("target_per_sec must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if decision_ttl <= 0:
            raise ValueError("decision_ttl must be > 0")
        self._rate = float(rate)
        self._mode = mode
        self._target_per_sec = float(target_per_sec)
        self._window_seconds = float(window_seconds)
        self._control_seconds = self._window_seconds / _CONTROL_DIVISOR
        self._clock = clock
        self._window = SlidingWindow(window_seconds, _BUCKETS, clock)
        self._controller = RateController(target_per_sec, clock=clock)
        self._decisions = _DecisionCache(
            _DECISION_SHARDS, decision_ttl, _DECISION_SHARD_CAP, clock)
        self._counter_lock = threading.Lock()
        self._control_lock = threading.Lock()
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
        with self._counter_lock:
            previous = self._mode
            self._mode = mode
        if mode == MODE_ADAPTIVE and previous != MODE_ADAPTIVE:
            # 重新切入自适应：窗口读数、控制器档位、trace 决策都从头算，
            # 不背上次模式留下的旧账。
            self._window.reset()
            self._controller.reset()
            self._decisions.clear()
            self._last_control = self._clock()

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
        with self._counter_lock:
            mode = self._mode
            total = self._total
            sampled = self._sampled
        (window_total, window_sampled), _ = self._window.snapshot(
            (TOTAL_KEY, SAMPLED_KEY))
        return {
            "mode": mode,
            "rate": self.rate(),
            "target_per_sec": self._target_per_sec,
            "total": total,
            "sampled": sampled,
            "dropped": total - sampled,
            "window_total": window_total,
            "window_sampled": window_sampled,
            "updates": self._controller.updates(),
        }

    # ---- 内部实现 ----

    def _static_decision(self, trace_id):
        """固定比例：拿 trace_id 的稳定小数跟比例比大小。"""
        keep = trace_unit(trace_id) < self._rate
        with self._counter_lock:
            self._total += 1
            if keep:
                self._sampled += 1
        return keep

    def _adaptive_decision(self, trace_id):
        """自适应：trace 级稳定决策，记账与控制推进互不阻塞。"""
        unit = trace_unit(trace_id)
        now = self._clock()
        keep = self._decisions.decide(trace_id, unit,
                                      self._controller.rate(), now)
        # 决策产生的计数原子写进同一桶，sampled 永远是 total 的子集。
        self._window.add2(TOTAL_KEY, 1,
                          SAMPLED_KEY, 1 if keep else 0, now)
        with self._counter_lock:
            self._total += 1
            if keep:
                self._sampled += 1
        if now - self._last_control >= self._control_seconds:
            self._maybe_control(now)
        return keep

    def _maybe_control(self, now):
        """到点就推进控制器；控制锁内再次确认时间，并发下只推进一拍。"""
        with self._control_lock:
            if now - self._last_control < self._control_seconds:
                return
            self._last_control = now
            self._step(now)

    def _step(self, now):
        """把最近一窗的多键原子快照喂给控制器。"""
        (sampled_count, total_count), coverage = self._window.snapshot(
            (SAMPLED_KEY, TOTAL_KEY))
        if coverage > 0:
            self._controller.observe(sampled_count / coverage,
                                     total_count / coverage)
