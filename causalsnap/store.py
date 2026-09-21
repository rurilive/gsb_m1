"""多进程共享状态与各进程的本地事件日志。

共享单元对所有进程可见；每个进程把本地发生的事按序记进自己的
事件序列，序号从 0 起单调递增。当前只记顺序，不追因果。
"""

import threading
import time


class Event:
    """一条本地事件记录。

    proc: 记下它的进程名
    seq: 该进程内的序号，从 0 起
    payload: 事件内容
    at: 落笔时刻，取自创建存储时注入的 clock
    """

    __slots__ = ("proc", "seq", "payload", "at")

    def __init__(self, proc, seq, payload, at):
        self.proc = proc
        self.seq = seq
        self.payload = payload
        self.at = at

    def __repr__(self):
        return "Event(proc=%r, seq=%d, payload=%r)" % (self.proc, self.seq, self.payload)

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return (self.proc, self.seq) == (other.proc, other.seq)

    def __hash__(self):
        return hash((self.proc, self.seq))


class CausalStore:
    """多进程共享的存储，注入时钟，一把锁保护。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        # proc -> [Event]，序号即下标，只增不减
        self._logs = {}
        # key -> value，所有进程共见
        self._cells = {}

    def record(self, proc, payload):
        """在 proc 本地记一个事件，返回它的序号。"""
        with self._lock:
            log = self._logs.setdefault(proc, [])
            event = Event(proc, len(log), payload, self._clock())
            log.append(event)
            return event.seq

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
