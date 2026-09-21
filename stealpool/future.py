"""Future：一次任务提交的凭据，带取消语义。"""

import threading
import time

from stealpool.errors import TaskCancelled

PENDING = "pending"
RUNNING = "running"
FINISHED = "finished"
CANCELLED = "cancelled"


class Future:
    """任务结果的占位符。

    状态流转：PENDING 起手，被 worker 取走后进 RUNNING，正常跑完进
    FINISHED；还在 PENDING 的可以取消，进 CANCELLED，其余状态取消返回 False。
    """

    def __init__(self):
        self._condition = threading.Condition()
        self._state = PENDING
        self._result = None
        self._exception = None
        self._callbacks = []

    @property
    def _settled(self):
        return self._state in (FINISHED, CANCELLED)

    def state(self):
        """返回当前状态字符串。"""
        with self._condition:
            return self._state

    def done(self):
        """完成或已被取消都算结束。"""
        with self._condition:
            return self._settled

    def running(self):
        with self._condition:
            return self._state == RUNNING

    def cancelled(self):
        with self._condition:
            return self._state == CANCELLED

    def cancel(self):
        """尝试取消，只有还在 PENDING 的任务能取消成功。"""
        with self._condition:
            if self._state != PENDING:
                return False
            self._state = CANCELLED
            self._condition.notify()
            callbacks = self._take_callbacks()
        self._fire(callbacks)
        return True

    def set_running_or_notify_cancel(self):
        """worker 取走任务时调用；返回 False 表示任务已被取消，别再执行。"""
        with self._condition:
            if self._state == CANCELLED:
                return False
            if self._state != PENDING:
                raise RuntimeError("这个 future 已经启动过了")
            self._state = RUNNING
            return True

    def set_result(self, value):
        """任务正常结束时写入结果。"""
        self._settle(result=value)

    def set_exception(self, exc):
        """任务抛异常时写入异常。"""
        self._settle(exception=exc)

    def result(self, timeout=None):
        """阻塞取结果；被取消抛 TaskCancelled，任务抛过异常就重新抛出。"""
        with self._condition:
            self._await(timeout)
            self._raise_if_failed()
            return self._result

    def exception(self, timeout=None):
        """阻塞取异常，正常结束返回 None，被取消抛 TaskCancelled。"""
        with self._condition:
            self._await(timeout)
            if self._state == CANCELLED:
                raise TaskCancelled("任务在开始前被取消")
            return self._exception

    def add_done_callback(self, fn):
        """结束（含被取消）时回调 fn(self)，已经结束就立即回调。"""
        with self._condition:
            callbacks = [fn] if self._settled else []
            if not callbacks:
                self._callbacks.append(fn)
        self._fire(callbacks)

    # 内部实现 ----------------------------------------------------------

    def _settle(self, result=None, exception=None):
        with self._condition:
            if self._state == FINISHED:
                raise RuntimeError("这个 future 已经有结果了")
            if self._state == CANCELLED:
                raise RuntimeError("这个 future 已经被取消")
            self._state = FINISHED
            if result is not None:
                self._result = result
            if exception is not None:
                self._exception = exception
            self._condition.notify()
            callbacks = self._take_callbacks()
        self._fire(callbacks)

    def _take_callbacks(self):
        callbacks, self._callbacks = self._callbacks, []
        return callbacks

    def _fire(self, callbacks):
        for fn in callbacks:
            fn(self)

    def _await(self, timeout):
        if timeout is None:
            while not self._settled:
                self._condition.wait()
            return
        deadline = time.monotonic() + timeout
        while not self._settled:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("等待任务结果超时")
            self._condition.wait(remaining)

    def _raise_if_failed(self):
        if self._state == CANCELLED:
            raise TaskCancelled("任务在开始前被取消")
        if self._exception is not None:
            raise self._exception
