"""多进程共享状态与各进程的本地事件日志。

共享单元对所有进程可见；每个进程把本地发生的事按序记进自己的
事件序列，序号从 0 起单调递增。事件带向量时钟，跨进程收发用
observe 并入，可比因果先后，也可取一致性快照。
"""

import threading
import time


class Event:
    """一条本地事件记录。

    proc: 记下它的进程名
    seq: 该进程内的序号，从 0 起
    payload: 事件内容
    at: 落笔时刻，取自创建存储时注入的 clock
    vclock: 落笔时本进程的向量时钟副本 {进程名: 已知条数}
    """

    __slots__ = ("proc", "seq", "payload", "at", "vclock")

    def __init__(self, proc, seq, payload, at, vclock=None):
        self.proc = proc
        self.seq = seq
        self.payload = payload
        self.at = at
        self.vclock = dict(vclock) if vclock is not None else {proc: seq + 1}

    def __repr__(self):
        return "Event(proc=%r, seq=%d, payload=%r)" % (self.proc, self.seq, self.payload)

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return (self.proc, self.seq) == (other.proc, other.seq)

    def __hash__(self):
        return hash((self.proc, self.seq))


def _compare_vectors(x, y):
    """比两份向量时钟：x 相对 y 是 before/after/concurrent/equal。"""
    less = greater = False
    for name in set(x) | set(y):
        a, b = x.get(name, 0), y.get(name, 0)
        if a < b:
            less = True
        elif a > b:
            greater = True
    if less and greater:
        return "concurrent"
    if less:
        return "before"
    if greater:
        return "after"
    return "equal"


def compare(a, b):
    """判两条事件的因果先后，返回 before/after/concurrent/equal。"""
    return _compare_vectors(a.vclock, b.vclock)


class Snapshot:
    """observer 视角的一致性快照，只含它已知的本地事件。

    observer: 取快照的进程名
    cut: {进程名: 算到第几条}，该进程前 n 条本地事件进入快照
    events: {进程名: (Event, ...)}，按进程分组的已知本地事件
    """

    __slots__ = ("observer", "cut", "events")

    def __init__(self, observer, cut, events):
        self.observer = observer
        self.cut = cut
        self.events = events

    def compare(self, other):
        """与另一份快照比新旧，返回 newer/older/concurrent/equal。

        各看见各的（cut 互不包含）即并发，不硬排先后。
        """
        relation = _compare_vectors(self.cut, other.cut)
        return {"before": "older", "after": "newer"}.get(relation, relation)


class CausalStore:
    """多进程共享的存储，注入时钟，一把锁保护。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # proc -> [Event]，序号即下标，只增不减
        self._logs = {}
        # proc -> {proc: 已知条数}，各进程的向量时钟
        self._vclocks = {}
        # key -> value，所有进程共见
        self._cells = {}

    def record(self, proc, payload):
        """在 proc 本地记一个事件，返回它的序号。"""
        with self._lock:
            log = self._logs.setdefault(proc, [])
            vclock = self._vclocks.setdefault(proc, {})
            vclock[proc] = vclock.get(proc, 0) + 1
            event = Event(proc, len(log), payload, self._clock(), vclock)
            log.append(event)
            return event.seq

    def observe(self, proc, src, seq):
        """proc 收到 src 的第 seq 条事件，把其向量时钟并进自己的历史。"""
        with self._lock:
            log = self._logs.get(src, ())
            if not 0 <= seq < len(log):
                raise IndexError("no event from %r at seq %d" % (src, seq))
            event = log[seq]
            vclock = self._vclocks.setdefault(proc, {})
            for name, count in event.vclock.items():
                if vclock.get(name, 0) < count:
                    vclock[name] = count
            return event

    def snapshot(self, observer):
        """取 observer 视角的一致性快照，只含它已知的本地事件。

        cut 即 observer 当前的向量时钟；向量时钟对因果历史闭合，
        所以切点不会停在半截事件上。
        """
        with self._lock:
            cut = {
                name: count
                for name, count in self._vclocks.get(observer, {}).items()
                if count
            }
            events = {
                name: tuple(self._logs.get(name, ())[:count])
                for name, count in cut.items()
            }
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
