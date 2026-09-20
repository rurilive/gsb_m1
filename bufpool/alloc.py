"""朴实分配器：每次 acquire 都新开一段内存，release 之后交给 GC。"""

import threading
import time

from bufpool.buffer import Buffer
from bufpool.errors import UnknownBuffer
from bufpool.stats import AllocStats
from bufpool.tiers import check_size

DEFAULT_CLOCK = time.monotonic


class _Lease:
    __slots__ = ("buffer", "size", "acquired_at")

    def __init__(self, buffer, size, acquired_at):
        self.buffer = buffer
        self.size = size
        self.acquired_at = acquired_at


class Allocator:
    """每次请求都新分配 bytearray，释放即丢弃。

    clock 可注入（返回秒数的可调用对象），默认 time.monotonic。
    借出记录里留着缓冲对象本身，所以释放动作只能来自本分配器发出去的缓冲。
    """

    def __init__(self, clock=None):
        self._clock = clock or DEFAULT_CLOCK
        self._lock = threading.Lock()
        self._out = {}
        self._next_serial = 1
        self._stats = AllocStats()

    @property
    def clock(self):
        return self._clock

    def acquire(self, size):
        """取一段容量不小于 size 的缓冲，内容全零。"""
        check_size(size)
        data = bytearray(size)
        with self._lock:
            serial = self._next_serial
            self._next_serial += 1
            buffer = Buffer(data, size, serial)
            self._out[id(buffer)] = _Lease(buffer, size, self._clock())
            self._stats.record_acquire(size)
        return buffer

    def release(self, buffer):
        """归还缓冲。不属于本分配器或重复归还都抛 UnknownBuffer。"""
        with self._lock:
            lease = self._out.pop(id(buffer), None)
            if lease is None:
                raise UnknownBuffer("不在本分配器的借出记录里: %r" % (buffer,))
            self._stats.record_release(lease.size)

    def outstanding(self, now=None):
        """在借缓冲的 (序号, 请求容量, 已持有秒数)，按序号排序。"""
        moment = self._clock() if now is None else now
        with self._lock:
            rows = [(lease.buffer.serial, lease.size,
                     max(0.0, moment - lease.acquired_at))
                    for lease in self._out.values()]
        rows.sort()
        return rows

    def stats(self):
        """当前计数快照，live 等于在借数量。"""
        return self._stats.snapshot()
