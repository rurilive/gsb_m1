"""多进程共享状态与各进程的本地事件日志。

共享单元对所有进程可见；每个进程把本地发生的事按序记进自己的
事件序列，序号从 0 起单调递增。事件带向量时钟，跨进程的先后靠
observe 传播；snapshot 取观察者已知事件拼成的一致性切面。
"""

import threading
import time


class Event:
    """一条本地事件记录。

    proc: 记下它的进程名
    seq: 该进程内的序号，从 0 起
    payload: 事件内容
    at: 落笔时刻，取自创建存储时注入的 clock
    clock: 落笔时记录进程的向量时钟（proc -> 已知的最大序号）
    """

    __slots__ = ("proc", "seq", "payload", "at", "clock")

    def __init__(self, proc, seq, payload, at, clock=None):
        self.proc = proc
        self.seq = seq
        self.payload = payload
        self.at = at
        self.clock = dict(clock) if clock else {}

    def __repr__(self):
        return "Event(proc=%r, seq=%d, payload=%r)" % (self.proc, self.seq, self.payload)

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return (self.proc, self.seq) == (other.proc, other.seq)

    def __hash__(self):
        return hash((self.proc, self.seq))


class Snapshot:
    """一份一致性快照：某个观察者已知的本地事件拼成的全局切面。

    observer: 取快照的进程名
    cut: proc -> 该进程的本地事件算到第几条（含）
    events: proc -> 该进程被收进快照的事件元组
    """

    def __init__(self, observer, cut, events):
        self.observer = observer
        self.cut = dict(cut)
        self.events = {proc: tuple(group) for proc, group in events.items()}

    def compare(self, other):
        """与另一份快照比新旧：newer/older/concurrent/equal，并发不硬排。"""
        procs = set(self.cut) | set(other.cut)
        le = all(self.cut.get(p, -1) <= other.cut.get(p, -1) for p in procs)
        ge = all(self.cut.get(p, -1) >= other.cut.get(p, -1) for p in procs)
        if le and ge:
            return "equal"
        if le:
            return "older"
        if ge:
            return "newer"
        return "concurrent"

    def __repr__(self):
        return "Snapshot(observer=%r, cut=%r)" % (self.observer, self.cut)


class CausalStore:
    """多进程共享的存储，注入时钟，一把锁保护。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # proc -> [Event]，序号即下标，只增不减
        self._logs = {}
        # proc -> {proc: 已知的最大序号}，记录进程当前的向量时钟
        self._knowledge = {}
        # key -> value，所有进程共见
        self._cells = {}

    def record(self, proc, payload):
        """在 proc 本地记一个事件，返回它的序号。"""
        with self._lock:
            log = self._logs.setdefault(proc, [])
            known = self._knowledge.setdefault(proc, {})
            known[proc] = len(log)
            event = Event(proc, len(log), payload, self._clock(), clock=known)
            log.append(event)
            return event.seq

    def observe(self, proc, src, seq):
        """proc 收到 src 的第 seq 条事件，把它的向量时钟并进 proc 的知识。"""
        with self._lock:
            log = self._logs.get(src)
            if log is None or not 0 <= seq < len(log):
                raise ValueError("没有 %r 的第 %d 条事件" % (src, seq))
            known = self._knowledge.setdefault(proc, {})
            for other, upto in log[seq].clock.items():
                if known.get(other, -1) < upto:
                    known[other] = upto

    def compare(self, a, b):
        """判两条事件的因果序：before/after/concurrent/equal。"""
        if a == b:
            return "equal"
        clock_a = self._clock_of(a)
        clock_b = self._clock_of(b)
        procs = set(clock_a) | set(clock_b)
        a_le = all(clock_a.get(p, -1) <= clock_b.get(p, -1) for p in procs)
        b_le = all(clock_b.get(p, -1) <= clock_a.get(p, -1) for p in procs)
        if a_le and b_le:
            return "equal"
        if a_le:
            return "before"
        if b_le:
            return "after"
        return "concurrent"

    @staticmethod
    def _clock_of(event):
        clock = dict(event.clock)
        clock.setdefault(event.proc, event.seq)
        return clock

    def snapshot(self, observer):
        """取 observer 当前所知的一致快照，只含它已知的本地事件。"""
        with self._lock:
            known = self._knowledge.get(observer, {})
            cut = {}
            events = {}
            for proc in sorted(known):
                upto = known[proc]
                included = tuple(e for e in self._logs.get(proc, ()) if e.seq <= upto)
                if included:
                    cut[proc] = upto
                    events[proc] = included
            return Snapshot(observer, cut, events)

    def local(self, proc):
        """返回 proc 的本地事件序列，元组副本，调用方随便改。"""
        with self._lock:
            return tuple(self._logs.get(proc, ()))

    def last(self, proc):
        """返回 proc 最近一条事件，还没有事件则返回 None。"""
        with self._lock:
            log = self._logs.get(proc)
            return log[-1] if log else None

    def processes(self):
        """出现过的进程名，字典序。"""
        with self._lock:
            return tuple(sorted(self._logs))

    def publish(self, proc, key, value):
        """把 value 写进共享单元 key。"""
        with self._lock:
            self._cells[key] = value

    def fetch(self, key, default=None):
        """读共享单元 key，没有则返回 default。"""
        with self._lock:
            return self._cells.get(key, default)

    def cells(self):
        """共享单元当前的 key，字典序。"""
        with self._lock:
            return tuple(sorted(self._cells))
