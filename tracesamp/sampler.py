"""链路追踪采样器：按 trace 决定整条调用链采不采。

静态模式按固定比例采样；自适应模式看窗口吞吐动态调采样率，把每秒采样条数
往 target_per_sec 上带。两种模式都只认 trace_id，同一个 trace 的多个 span
永远拿到同一个结论。

自适应路径拆成三件互不阻塞的事：

决策
    拿 trace_id 在 ``DecisionCache`` 里查/建一次结论。结论由
    ``trace_unit(trace_id) < 当前采样率`` 给出，跟静态模式同一套确定性
    算法，缓存之后同一条 trace 前后差几秒到齐、几十个 span 挤进来都
    拿到同一个 bool。缓存分片，各带一把小锁，热路径不跨片竞争。
统计
    span 计数写进线程本地计数器，定期批量合并进滑动窗口，热路径上
    没有任何共享锁（线程本地数组首次登记时短暂加锁一次）。
控制
    每 1/4 窗口时长由一个抢到执行权的线程做一次窗口快照（total、
    sampled 在同一把锁里读出），算 horizon 后交给 RateController
    反演下一个采样率。决策线程读到的是一个原子引用，不需要锁。
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

# 统计窗口切成几格：1/4 秒滚一格，快照在稳态下覆盖完整的 1 秒。
_BUCKETS = 4
# 控制间隔取窗口的四分之一，由某个 span 线程顺带执行，不另起线程。
_CONTROL_DIVISOR = 4

# 决策缓存：16 个分片，每片当代最多 16384 条 trace，到龄或写满时
# 整体换“代”（旧代再活一代）。每秒十万 span、平均每条 trace 3 个
# span 时约 3.3 万新 trace/秒，每片约 2000 条/秒，一代能撑约 8 秒，
# 两代合计罩住十几秒内到齐的 span，足够正常 trace 的到齐间隔。
_CACHE_SHARDS = 16
_CACHE_GENERATION_CAPACITY = 16384
_CACHE_GENERATION_TTL = 5.0

# 起步阶段的快速控制：攒够这个条数就先算一次，避免开闸初期过采。
_WARMUP_SPANS = 128
# 起步折算速率的最小时间分母：只防同一时刻挤进来的一批 span 出现
# 零时长除零，正常推进的时钟不受它影响。
_WARMUP_MIN_HORIZON = 0.001

_MISS = object()


def trace_unit(trace_id):
    """把 trace_id 落到 [0, 1) 上的一个稳定小数。

    走 crc32，不走内置 hash，同一个 trace_id 换进程、换机器都是同一个值。
    """
    digest = zlib.crc32(str(trace_id).encode("utf-8"))
    return digest / 0x100000000


class _ThreadCounters:
    """线程本地的 (total, sampled) 计数器，热路径无锁。

    每个线程在自己的本地槽里累加，控制 tick 时一次性把所有线程的
    增量合并进滑动窗口。
    """

    def __init__(self):
        self._local = threading.local()
        self._slots = []
        self._slots_lock = threading.Lock()

    def add(self, sampled):
        """记一次决策，sampled 是这次采没采。"""
        slot = getattr(self._local, "slot", None)
        if slot is None:
            slot = [0, 0]
            self._local.slot = slot
            with self._slots_lock:
                self._slots.append(slot)
        slot[0] += 1
        if sampled:
            slot[1] += 1

    def drain(self):
        """取走所有线程的累计增量，返回 (total, sampled)。"""
        total = 0
        sampled = 0
        with self._slots_lock:
            for slot in self._slots:
                total += slot[0]
                sampled += slot[1]
                slot[0] = 0
                slot[1] = 0
        return total, sampled

    def totals(self):
        """读累计计数不清零，给 stats() 用。"""
        total = 0
        sampled = 0
        with self._slots_lock:
            for slot in self._slots:
                total += slot[0]
                sampled += slot[1]
        return total, sampled

    def reset(self):
        """清掉所有线程槽里的累计。"""
        with self._slots_lock:
            for slot in self._slots:
                slot[0] = 0
                slot[1] = 0


class DecisionCache:
    """trace 级决策缓存：trace_id -> 采不采，分片 + 双代轮换。

    每个分片有两代普通 dict：新 trace 写当代，老 trace 留在旧代。
    当代到龄或写满时整体滚一代：旧代直接丢弃，当代降为旧代，
    开一个空当代。没有逐条 TTL、没有 LRU 链表，写临界区只有一次
    dict 赋值，十万 span/秒峰值下也不成为瓶颈。

    命中路径无锁：dict 读在锁外；未命中时在锁外做完决策（crc32
    不便宜），再在分片锁内 double-check 后放进当代，按需换代。
    """

    def __init__(self, decide, shards=_CACHE_SHARDS,
                 generation_capacity=_CACHE_GENERATION_CAPACITY,
                 generation_ttl=_CACHE_GENERATION_TTL, clock=time.monotonic):
        self._decide = decide
        self._shards = shards
        self._capacity = int(generation_capacity)
        self._ttl = float(generation_ttl)
        self._clock = clock
        started = clock()
        # 每片：[当代 dict, 旧代 dict]，born_at 是当代出生时刻
        self._generations = [[dict(), dict()] for _ in range(shards)]
        self._born_at = [started for _ in range(shards)]
        self._locks = [threading.Lock() for _ in range(shards)]

    def get(self, trace_id):
        """取这条 trace 的结论，没有就现场生成并记住。"""
        shard = hash(trace_id) % self._shards
        generations = self._generations[shard]
        decision = generations[0].get(trace_id, _MISS)
        if decision is _MISS:
            decision = generations[1].get(trace_id)
            from_previous = True
        else:
            from_previous = False
        if decision is not None:
            if from_previous:
                # 命中旧代说明这条 trace 仍活跃：把它带回当代，否则
                # 下次换代时它会被丢弃，采样率一变重算就跟早先 span
                # 拿到的结论打架（同一 trace 一半采一半丢）。
                self._promote_from_previous(shard, trace_id, decision)
            return decision
        # 决策放在锁外做（crc32 不便宜），锁内只 double-check + 记账
        decision = self._decide(trace_id)
        with self._locks[shard]:
            current, previous = generations
            if trace_id in current or trace_id in previous:
                return decision
            now = self._clock()
            if (len(current) >= self._capacity
                    or now - self._born_at[shard] >= self._ttl):
                # 换代：旧代丢弃，当代降为旧代，空 dict 当当代
                generations[1] = current
                current = dict()
                generations[0] = current
                self._born_at[shard] = now
            current[trace_id] = decision
            return decision

    def _promote_from_previous(self, shard, trace_id, decision):
        """旧代命中的活跃条目带回当代；当代到龄/写满就先换代。"""
        with self._locks[shard]:
            generations = self._generations[shard]
            current, previous = generations
            if trace_id in current:
                return
            now = self._clock()
            if (len(current) >= self._capacity
                    or now - self._born_at[shard] >= self._ttl):
                generations[1] = current
                current = dict()
                generations[0] = current
                self._born_at[shard] = now
            if previous.pop(trace_id, None) is not None:
                current[trace_id] = decision

    def __len__(self):
        """各分片两代条目数之和，测试/巡检用。"""
        return sum(len(generations[0]) + len(generations[1])
                   for generations in self._generations)

    def clear(self):
        """清空全部结论。"""
        now = self._clock()
        for shard in range(self._shards):
            with self._locks[shard]:
                self._generations[shard] = [dict(), dict()]
                self._born_at[shard] = now


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
        self._bucket_seconds = self._window_seconds / _BUCKETS
        self._control_seconds = self._window_seconds / _CONTROL_DIVISOR
        self._clock = clock
        self._window = SlidingWindow(window_seconds, _BUCKETS, clock)
        self._controller = RateController(target_per_sec, clock=clock)
        self._counters = _ThreadCounters()
        self._cache = DecisionCache(self._decide_at_current_rate, clock=clock)
        # 控制 tick 由命中时间点的 span 线程竞争执行，只让一个线程进；
        # stats() 也借它跟 drain 互斥，避免同一批计数被算两次。
        self._control_lock = threading.Lock()
        self._last_control = clock()
        self._first_traffic_at = None
        self._primed = False
        # 已经从线程本地槽合并出来的累计账：stats 的 total/sampled 是
        # 进程级累计，不能用会随时间过期的窗口计数代替。
        self._drained_total = 0
        self._drained_sampled = 0

    # ---- 对外接口 ----

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        """切换采样模式，静态比例和自适应的账各算各的。"""
        if mode not in MODES:
            raise ValueError("unknown mode: %r" % (mode,))
        self._mode = mode
        if mode == MODE_ADAPTIVE:
            # 自适应账重新起算：窗口、决策缓存、控制器都回到干净状态，
            # 不把上一段（静态或上一轮自适应）的旧账带进新的一轮。
            self._window.reset()
            self._cache.clear()
            self._controller.reset()
            self._last_control = self._clock()
            self._first_traffic_at = None
            self._primed = False
            self._drained_total = 0
            self._drained_sampled = 0
            self._counters.reset()

    def rate(self):
        """当前生效的采样率。"""
        if self._mode == MODE_STATIC:
            return self._rate
        return self._controller.rate()

    def should_sample(self, trace_id):
        """这条 trace 的 span 要不要采。"""
        if self._mode == MODE_STATIC:
            keep = trace_unit(trace_id) < self._rate
            self._counters.add(keep)
            return keep
        return self._adaptive_decision(trace_id)

    def stats(self):
        """当前状态快照，监控面板直接读它。"""
        # 跟控制 tick 互斥一下：drain 会把 pending 搬进窗口，不互斥的话
        # 同一批计数可能在窗口里和 pending 里各被算一次。
        with self._control_lock:
            pending_total, pending_sampled = self._counters.totals()
            window_counts = self._window.snapshot((TOTAL_KEY, SAMPLED_KEY))
        total = self._drained_total + pending_total
        sampled = self._drained_sampled + pending_sampled
        return {
            "mode": self._mode,
            "rate": self.rate(),
            "target_per_sec": self._target_per_sec,
            "total": total,
            "sampled": sampled,
            "dropped": total - sampled,
            "window_total": window_counts[TOTAL_KEY],
            "window_sampled": window_counts[SAMPLED_KEY],
            "updates": self._controller.updates(),
        }

    # ---- 自适应内部实现 ----

    def _decide_at_current_rate(self, trace_id):
        """首次见到这条 trace 时的决策：跟静态模式同一套确定性算法。

        不掷随机骰子：trace_unit 是 trace_id 的稳定散列，结论只取决于
        trace_id 和当前采样率，缓存后同一 trace 永远一致；换进程/机器
        只要采样率相同，结论也相同。
        """
        return trace_unit(trace_id) < self._controller.rate()

    def _adaptive_decision(self, trace_id):
        keep = self._cache.get(trace_id)
        self._counters.add(keep)
        now = self._clock()
        if self._first_traffic_at is None:
            self._first_traffic_at = now
        if not self._primed:
            # 起步阶段窗口还没攒满，快速先算一次，别按 1.0 过量采样
            self._maybe_warmup_control(now)
        elif now - self._last_control >= self._control_seconds:
            # 多线程同时到点：非阻塞抢锁，抢不到的线程直接放行，
            # 不在 span 热路径上排队等控制计算。
            if self._control_lock.acquire(blocking=False):
                try:
                    if now - self._last_control >= self._control_seconds:
                        self._run_control(now)
                finally:
                    self._control_lock.release()
        return keep

    def _maybe_warmup_control(self, now):
        """攒够 _WARMUP_SPANS 条就做首次控制，_primed 在锁内置位。"""
        # 起步阶段窗口必然是空的（还没做过控制 tick），只看各线程
        # pending 的累计就够，不用每 span 去抢窗口锁。
        pending_total, _ = self._counters.totals()
        if pending_total < _WARMUP_SPANS:
            return
        if self._control_lock.acquire(blocking=False):
            try:
                if not self._primed:
                    self._run_control(now)
                    self._primed = True
            finally:
                self._control_lock.release()

    def _run_control(self, now):
        """合并线程本地计数 -> 拍一致快照 -> 喂给控制器。

        调用方必须已持有 _control_lock。
        """
        if self._primed and now - self._last_control < self._control_seconds:
            return
        pending_total, pending_sampled = self._counters.drain()
        if pending_total:
            self._drained_total += pending_total
            self._drained_sampled += pending_sampled
            self._window.add_many({TOTAL_KEY: pending_total,
                                   SAMPLED_KEY: pending_sampled})
        counts = self._window.snapshot((TOTAL_KEY, SAMPLED_KEY))
        total = counts[TOTAL_KEY]
        sampled = counts[SAMPLED_KEY]
        if total <= 0:
            # 窗口空：保持当前采样率，下次流量出现重新记起步时间
            self._first_traffic_at = None
            self._last_control = now
            return
        # horizon 是这批计数实际覆盖的时长：起步阶段窗口没攒满，
        # 按满窗 1 秒去折算速率会把吞吐估小一个数量级，采样率
        # 一步就被拽到底（压测里见过的那个现象）。
        if self._first_traffic_at is None:
            horizon = self._window_seconds
        else:
            horizon = min(self._window_seconds,
                          max(now - self._first_traffic_at,
                              _WARMUP_MIN_HORIZON))
        self._controller.observe(sampled / horizon, total / horizon)
        self._last_control = now
