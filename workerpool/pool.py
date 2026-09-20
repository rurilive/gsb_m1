"""固定大小线程池。

submit 把任务放进队列，size 个常驻工作线程逐个领取执行；
每个任务对应一个 Task 句柄，用来查状态、等落定、取结果。
close 做优雅关闭：拒收新任务，等已提交任务落定或按宽限取消。
"""

import atexit as _atexit
import queue
import threading
import time
from typing import NamedTuple

PENDING = "pending"
RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"
CANCELLED = "cancelled"


class PoolClosed(Exception):
    """向已关闭的池提交任务时抛出。"""


class ShutdownReport(NamedTuple):
    """close 的返回报告。

    completed: 本次 close 期间落定的任务数（close 前已落定的不计）。
    cancelled: 宽限到期仍未落定、被标记取消的任务句柄列表。
    """

    completed: int
    cancelled: list


class Task:
    """一次任务提交的句柄：状态、等待、结果。

    句柄在 submit 时创建，与执行进度无关；主线程拿到的
    Task 立刻可用，后续所有方法都线程安全。
    """

    def __init__(self, fn, args, kwargs, seq=0):
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._seq = seq
        self._lock = threading.Lock()
        self._state = PENDING
        self._result = None
        self._exception = None
        self._done = threading.Event()

    def __repr__(self):
        return f"<Task #{self._seq} {self._state}>"

    @property
    def fn(self):
        return self._fn

    @property
    def seq(self):
        """提交序号，从 0 起，池内单调递增。"""
        return self._seq

    @property
    def state(self):
        """PENDING / RUNNING / FINISHED / FAILED / CANCELLED 之一。"""
        return self._state

    @property
    def done(self):
        """任务是否已落定（成功或失败都算）。"""
        return self._done.is_set()

    def wait(self, timeout=None):
        """等任务落定，返回是否在时限内落定。"""
        return self._done.wait(timeout)

    def result(self, timeout=None):
        """阻塞取结果；任务内抛出的异常在这里原样抛出。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self, timeout=None):
        """阻塞取异常对象；任务成功时返回 None。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        return self._exception

    def _run(self):
        # 只由工作线程调用：置状态、执行、写回结果。
        # 任务内异常在这里兜住，不向上杀死工作线程。
        with self._lock:
            if self._state == CANCELLED:
                return
            self._state = RUNNING
        try:
            result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            with self._lock:
                if self._state != CANCELLED:
                    self._exception = exc
                    self._state = FAILED
        else:
            with self._lock:
                if self._state != CANCELLED:
                    self._result = result
                    self._state = FINISHED
        self._done.set()

    def _cancel(self):
        # 只由 close 调用：未落定任务标记 CANCELLED，唤醒等待者。
        # 已落定的不动；返回是否本次新取消。
        with self._lock:
            if self._state in (FINISHED, FAILED, CANCELLED):
                return False
            self._state = CANCELLED
        self._done.set()
        return True


class WorkerPool:
    """固定大小线程池：size 个常驻线程共享一个任务队列。

    并发上限就是 size，多余的提交在队列里排队。
    close(grace_timeout) 优雅关闭；atexit=True 时退出自动收尾。
    """

    def __init__(self, size, atexit=True):
        if size < 1:
            raise ValueError("size must be >= 1")
        self._queue = queue.SimpleQueue()
        self._tasks = []
        self._seq = 0
        self._closed = False
        self._report = None
        self._close_lock = threading.Lock()
        self._report_ready = threading.Event()
        self._workers = [
            threading.Thread(target=self._worker_loop, daemon=True)
            for _ in range(size)
        ]
        for w in self._workers:
            w.start()
        self._atexit_registered = False
        if atexit:
            _atexit.register(self.close)
            self._atexit_registered = True

    @property
    def size(self):
        return len(self._workers)

    @property
    def atexit_registered(self):
        """是否已在 atexit 注册退出时的自动 close。"""
        return self._atexit_registered

    @property
    def tasks(self):
        """全部已提交任务的句柄快照，按提交顺序；外部改不了内部列表。"""
        return tuple(self._tasks)

    def submit(self, fn, *args, **kwargs):
        """提交任务，立即返回句柄，不等待执行。"""
        with self._close_lock:
            if self._closed:
                raise PoolClosed("pool is closed")
            task = Task(fn, args, kwargs, seq=self._seq)
            self._seq += 1
            self._tasks.append(task)
            self._queue.put(task)
            return task

    def map(self, fn, *iterables):
        """批量提交，阻塞到全部完成，按提交顺序返回结果列表。"""
        if self._closed:
            raise PoolClosed("pool is closed")
        tasks = [self.submit(fn, *item) for item in zip(*iterables)]
        return [t.result() for t in tasks]

    def close(self, grace_timeout=None):
        """优雅关闭：拒收新任务，收尾已提交任务，返回关闭报告。

        grace_timeout 为 None 时不限时，等全部已提交任务落定；
        否则等到期，未落定者（含排队中的）标记 CANCELLED 且不再执行。
        重复调用幂等，返回首次关闭的报告。
        """
        with self._close_lock:
            if self._report is not None:
                return self._report
            if self._closed:
                owner = False
            else:
                self._closed = True
                owner = True
                pending = [t for t in self._tasks if not t.done]
        if not owner:
            # 另一个线程正在 close：等它出报告，返回同一份。
            self._report_ready.wait()
            return self._report

        deadline = None if grace_timeout is None else time.monotonic() + grace_timeout
        for t in pending:
            left = None if deadline is None else max(0.0, deadline - time.monotonic())
            t.wait(left)
        cancelled = [t for t in pending if not t.done and t._cancel()]
        report = ShutdownReport(
            completed=len(pending) - len(cancelled), cancelled=cancelled
        )
        with self._close_lock:
            self._report = report
        self._report_ready.set()
        return report

    def wait_all(self, timeout=None):
        """等全部已提交任务落定，返回是否在时限内全部落定。

        只等待、不改变任何状态，也不影响新提交。
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        for t in self._tasks:
            if t.done:
                continue
            left = None if deadline is None else deadline - time.monotonic()
            if not t.wait(left):
                return False
        return True

    def _worker_loop(self):
        # 常驻循环：队列空就阻塞等待，线程是 daemon，不阻塞进程退出。
        while True:
            task = self._queue.get()
            task._run()
