"""调度器：提交任务、驱动事件循环、维护定时器记录。"""

import itertools
import time

from .loop import EventLoop
from .task import Task


class Scheduler:
    """轻量任务调度器。时间从注入的时钟读，定时全挂在事件循环的堆上。"""

    def __init__(self, clock=time.monotonic):
        self._loop = EventLoop(clock)
        self._tasks = {}
        self._timers = {}
        self._ids = itertools.count(1)

    def now(self):
        return self._loop.now()

    def submit(self, name, body, *, delay=0.0, timeout=None, on_done=None):
        """提交一个根任务，delay 秒后开工，timeout 是从提交算起的总预算。"""
        return self._spawn(None, name, body, delay, timeout, on_done)

    def _spawn(self, parent, name, body, delay, timeout, on_done):
        task = Task(self, next(self._ids), name, body,
                    delay=delay, timeout=timeout, parent=parent)
        self._tasks[task.id] = task
        if parent is not None:
            parent.children.append(task)
            parent._open_children += 1
        if delay > 0:
            handle = self._loop.call_later(delay, task._start)
            self._timers.setdefault(task.id, {})["start"] = handle
        else:
            self._loop.call_soon(task._start)
        if timeout is not None:
            handle = self._loop.call_later(timeout, self._on_deadline, task.id)
            self._timers.setdefault(task.id, {})["deadline"] = handle
        if on_done is not None:
            task.add_done_callback(on_done)
        return task

    def _on_deadline(self, task_id):
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.cancel("timeout")

    def _notify_parent(self, parent, child):
        self._loop.call_soon(parent._child_settled, child)

    def _drop_timer(self, task_id, kind):
        """撤销任务名下的一类定时器。"""
        handle = self._timers.get(task_id, {}).pop(kind, None)
        if handle is not None:
            handle.cancel()

    def _forget_task(self, task_id):
        """任务落定之后，把它名下的定时器记录清掉。"""
        self._timers.pop(task_id, None)

    def run(self, block=False):
        """跑一轮事件，返回本次处理的事件数。"""
        return self._loop.run(block=block)

    def armed_timers(self):
        """还挂着、没有撤销的定时器数量。"""
        return self._loop.active_timers()

    def tasks(self):
        """提交过的全部任务，按 id 排。"""
        return [self._tasks[key] for key in sorted(self._tasks)]
