"""朴素定时器集合：手动推进时钟，取走到期任务。

当前实现把待触发的定时器全部放进一个列表，每次 tick 从头到尾线性扫描一遍
找出 deadline 到点的任务，取消也要逐个比对剔除。功能正确，但注册、取消与
推进的代价都随挂载总量线性增长，也没有分级结构或多级级联。
"""

import time


class TimerError(ValueError):
    """定时器相关错误的基类。

    继承 ValueError，这样基线的取值错误（delay 非正、时钟回拨）与新增实现
    抛出的定时器错误都能被同一个 except ValueError 捕获。
    """


class TimerHandle:
    """add() 返回的句柄，用它取消或查看定时器。"""

    __slots__ = ("payload", "priority", "deadline", "cancelled", "fired", "_timer")

    def __init__(self, payload, priority, deadline, timer):
        self.payload = payload
        self.priority = priority
        self.deadline = deadline
        self.cancelled = False
        self.fired = False
        self._timer = timer

    def cancel(self):
        return self._timer.cancel(self)

    def __repr__(self):
        if self.cancelled:
            state = "cancelled"
        elif self.fired:
            state = "fired"
        else:
            state = "pending"
        return "TimerHandle(payload=%r, deadline=%r, %s)" % (
            self.payload,
            self.deadline,
            state,
        )


class TimerSet:
    """最朴素的定时器集合：一个无序列表装全部待触发定时器。

    - TimerSet(clock=None)：clock 可注入，默认 time.monotonic
    - add(delay, payload=None, priority=0)：挂 delay 秒后触发的定时器，返回句柄
    - tick(now)：把时钟推进到 now，取走所有 deadline <= now 的到期句柄
    - cancel(handle)：取消定时器，已取消或已触发的返回 False
    - now、size：当前时钟与待触发定时器数
    """

    def __init__(self, clock=None):
        self._clock = clock or time.monotonic
        self._now = float(self._clock())
        self._handles = []

    @property
    def now(self):
        return self._now

    @property
    def size(self):
        return len(self._handles)

    def add(self, delay, payload=None, priority=0):
        if delay <= 0:
            raise ValueError("delay must be positive")
        deadline = self._now + delay
        handle = TimerHandle(payload, priority, deadline, self)
        self._handles.append(handle)
        return handle

    def tick(self, now):
        if now < self._now:
            raise ValueError("clock cannot move backwards")
        self._now = float(now)
        due = []
        rest = []
        for handle in self._handles:
            if handle.cancelled:
                continue
            if handle.deadline <= self._now:
                handle.fired = True
                due.append(handle)
            else:
                rest.append(handle)
        # 线性扫描：先按 deadline 升序，同刻保持注册先后（列表扫描天然稳定）。
        due.sort(key=lambda h: h.deadline)
        self._handles = rest
        return due

    def cancel(self, handle):
        if handle.cancelled or handle.fired:
            return False
        if handle not in self._handles:
            return False
        self._handles.remove(handle)
        handle.cancelled = True
        return True
