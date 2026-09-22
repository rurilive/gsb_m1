"""最小事件循环：就绪队列加定时器堆，时间源可注入。"""

import heapq
import itertools
import time
from collections import deque


class TimerHandle:
    """一次定时排期。cancel 之后到点也不会再触发。"""

    __slots__ = ("deadline", "seq", "callback", "args", "cancelled")

    def __init__(self, deadline, seq, callback, args):
        self.deadline = deadline
        self.seq = seq
        self.callback = callback
        self.args = args
        self.cancelled = False

    def cancel(self):
        """撤销这次排期。"""
        self.cancelled = True

    @property
    def active(self):
        return not self.cancelled

    def __repr__(self):
        return "<TimerHandle at {} seq {} {}>".format(
            self.deadline, self.seq, "cancelled" if self.cancelled else "armed"
        )


class ManualClock:
    """显式推进的时钟，测试和演示拿它注入时间。"""

    def __init__(self, start=0.0):
        self._time = float(start)

    def __call__(self):
        return self._time

    def set(self, value):
        self._time = float(value)
        return self._time

    def advance(self, delta):
        self._time += float(delta)
        return self._time


class EventLoop:
    """就绪回调按 FIFO 执行，定时器按到期时刻和排期先后出堆。"""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._ready = deque()
        self._timers = []
        self._seq = itertools.count()
        self._now = 0.0

    def now(self):
        self._now = self._clock()
        return self._now

    def call_soon(self, callback, *args):
        """把回调排进就绪队列，本轮事件处理里按序执行。"""
        self._ready.append((callback, args))

    def call_at(self, deadline, callback, *args):
        """在绝对时刻 deadline 触发一次回调，返回可撤销的句柄。"""
        handle = TimerHandle(deadline, next(self._seq), callback, args)
        heapq.heappush(self._timers, (deadline, handle.seq, handle))
        return handle

    def call_later(self, delay, callback, *args):
        return self.call_at(self.now() + delay, callback, *args)

    def _drop_stale(self):
        while self._timers and self._timers[0][2].cancelled:
            heapq.heappop(self._timers)

    def next_deadline(self):
        """下一个有效定时器的到期时刻，没有就返回 None。"""
        self._drop_stale()
        if not self._timers:
            return None
        return self._timers[0][0]

    def active_timers(self):
        """还挂着、没有被撤销的定时器数量。"""
        return sum(1 for item in self._timers if not item[2].cancelled)

    def _pop_due(self, now):
        self._drop_stale()
        if not self._timers or self._timers[0][0] > now:
            return None
        return heapq.heappop(self._timers)[2]

    def run(self, block=False):
        """把当前能做的事做完。

        反复交替：先清空就绪队列，再触发一个到点的定时器，直到两者都
        腾不出来为止。block 为真时顺着注入时钟等最近一个到期时刻，
        只适合真实时钟；返回本次处理的事件数。
        """
        handled = 0
        while True:
            while self._ready:
                callback, args = self._ready.popleft()
                callback(*args)
                handled += 1
            due = self._pop_due(self.now())
            if due is not None:
                due.callback(*due.args)
                handled += 1
                continue
            deadline = self.next_deadline()
            if deadline is None:
                return handled
            if not block:
                return handled
            pause = deadline - self.now()
            if pause > 0:
                time.sleep(pause)
