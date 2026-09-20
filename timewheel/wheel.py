"""手动推进的时间轮：add 挂任务，advance 推时间，due 取到期任务。

轮子只负责到时收集，不执行任务。语义约定见 README，本文件与 README 有
出入时以 README 为准。
"""

import math
import time


class TaskHandle:
    """add() 返回的句柄，用它取消任务。"""

    __slots__ = ("task", "deadline", "slot", "cancelled", "_wheel")

    def __init__(self, task, deadline, slot, wheel):
        self.task = task
        self.deadline = deadline
        self.slot = slot
        self.cancelled = False
        self._wheel = wheel

    def cancel(self):
        return self._wheel.cancel(self)


class TimeWheel:
    """手动推进的时间轮。

    - add(delay, task)：挂任务，返回句柄；delay > 0 且不超过一整圈
    - advance(now)：把轮子推进到 now，逐槽收集到期任务（跨多槽不丢不重）
    - due()：取走就绪队列全部任务，按到期先后
    - cancel(handle)：任务在槽中或已进就绪队列均可取消
    """

    def __init__(self, slots=32, tick=1.0, clock=None):
        if slots < 2:
            raise ValueError("slots must be >= 2")
        if tick <= 0:
            raise ValueError("tick must be positive")
        self._slots = slots
        self._tick = tick
        self._clock = clock or time.monotonic
        self._now = float(self._clock())
        self._cursor = 0
        self._buckets = [[] for _ in range(slots)]
        self._ready = {}

    @property
    def now(self):
        return self._now

    def add(self, delay, task):
        if delay <= 0:
            raise ValueError("delay must be positive")
        if delay > self._slots * self._tick:
            raise ValueError("delay beyond one revolution")
        steps = int(math.ceil(delay / self._tick))
        idx = (self._cursor + steps) % (self._slots - 1)
        handle = TaskHandle(task, self._now + delay, idx, self)
        self._buckets[idx].append(handle)
        return handle

    def advance(self, now):
        if now < self._now:
            raise ValueError("timewheel cannot move backwards")
        steps = int((now - self._now) // self._tick)
        if steps <= 0:
            return
        new_cursor = (self._cursor + steps) % self._slots
        if self._cursor + steps < self._slots:
            for idx in range(self._cursor + 1, self._cursor + steps + 1):
                self._drain(idx)
        else:
            for idx in range(self._cursor + 1, self._slots):
                self._drain(idx)
            for idx in range(0, new_cursor):
                self._drain(idx)
        self._cursor = new_cursor
        self._now += steps * self._tick

    def due(self):
        out = [self._ready[key].task for key in sorted(self._ready)]
        self._ready.clear()
        return out

    def cancel(self, handle):
        if handle.cancelled:
            return False
        bucket = self._buckets[handle.slot]
        if handle in bucket:
            bucket.remove(handle)
            handle.cancelled = True
            return True
        return False

    def _drain(self, idx):
        bucket = self._buckets[idx]
        if not bucket:
            return
        self._buckets[idx] = []
        for handle in bucket:
            self._ready[handle.deadline] = handle
