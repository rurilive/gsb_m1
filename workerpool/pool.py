"""固定大小线程池。

submit 把任务放进队列，size 个常驻工作线程逐个领取执行；
每个任务对应一个 Task 句柄，用来查状态、等落定、取结果。

close(grace_timeout) 做优雅关闭：拒收新任务，等待已提交任务落定；
超过宽限期仍未落定的任务标记为 CANCELLED（排队的不再执行，
在跑的任其跑完但状态不再翻转）。
"""

import atexit as _atexit
import queue
import threading
import time

from concurrent.futures import CancelledError

PENDING = "pending"
RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"
CANCELLED = "cancelled"


class PoolClosed(RuntimeError):
    """池已优雅关闭，不再接收新任务（submit / map）。"""


class CloseReport(dict):
    """close() 报告：completed 为本次落定任务数，cancelled 为未完成句柄列表。

    既支持 report["completed"]，也支持 report.completed。
    """

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


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
        self._state = PENDING
        self._result = None
        self._exception = None
        self._done = threading.Event()
        self._lock = threading.Lock()

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
        if self._state == CANCELLED:
            raise CancelledError(f"task #{self._seq} cancelled during shutdown")
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self, timeout=None):
        """阻塞取异常对象；任务成功时返回 None。"""
        if not self._done.wait(timeout):
            raise TimeoutError("task not finished in time")
        if self._state == CANCELLED:
            raise CancelledError(f"task #{self._seq} cancelled during shutdown")
        return self._exception

    def _cancel(self):
        """关闭宽限期到期后由池调用。

        PENDING（含排队中）直接取消；RUNNING 的函数无法安全打断，
        同样标记取消——它会继续跑完，但状态不再翻转、结果被丢弃。
        返回 True 表示本调用完成了取消。
        """
        with self._lock:
            if self._done.is_set():
                return False
            self._state = CANCELLED
            self._done.set()
            return True

    def _run(self):
        # 只由工作线程调用：置状态、执行、写回结果。
        # 任务内异常在这里兜住，不向上杀死工作线程。
        with self._lock:
            if self._state == CANCELLED:
                # 出队前已在 close 超时后被取消，排队任务不再执行。
                return
            self._state = RUNNING
        try:
            result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            with self._lock:
                if self._state == CANCELLED:
                    return
                self._exception = exc
                self._state = FAILED
        else:
            with self._lock:
                if self._state == CANCELLED:
                    return
                self._result = result
                self._state = FINISHED
        self._done.set()


class WorkerPool:
    """固定大小线程池：size 个常驻线程共享一个任务队列。

    并发上限就是 size，多余的提交在队列里排队。
    atexit=True（默认）时向解释器注册退出钩子，进程退出时按
    close() 语义（无时限等待）收尾。
    """

    def __init__(self, size, atexit=True):
        if size < 1:
            raise ValueError("size must be >= 1")
        self._queue = queue.SimpleQueue()
        self._tasks = []
        self._seq = 0
        self._closed = False
        self._close_lock = threading.Lock()
        self._close_done = threading.Condition(self._close_lock)
        self._close_report = None
        self._workers = [
            threading.Thread(target=self._worker_loop, daemon=True)
            for _ in range(size)
        ]
        for w in self._workers:
            w.start()
        self._atexit_registered = False
        if atexit:
            _atexit.register(self._atexit_close)
            self._atexit_registered = True

    @property
    def size(self):
        return len(self._workers)

    @property
    def tasks(self):
        """全部已提交任务的句柄快照，按提交顺序；外部改不了内部列表。"""
        return tuple(self._tasks)

    @property
    def atexit_registered(self):
        """是否已向 atexit 注册退出收尾钩子。"""
        return self._atexit_registered

    def submit(self, fn, *args, **kwargs):
        """提交任务，立即返回句柄，不等待执行。"""
        with self._close_lock:
            if self._closed:
                raise PoolClosed("worker pool is closed; no new tasks accepted")
            task = Task(fn, args, kwargs, seq=self._seq)
            self._seq += 1
            self._tasks.append(task)
            self._queue.put(task)
            return task

    def map(self, fn, *iterables):
        """批量提交，阻塞到全部完成，按提交顺序返回结果列表。"""
        if self._closed:
            raise PoolClosed("worker pool is closed; no new tasks accepted")
        tasks = [self.submit(fn, *item) for item in zip(*iterables)]
        return [t.result() for t in tasks]

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

    def close(self, grace_timeout=None):
        """优雅关闭池并返回报告（重复调用幂等，返回首次报告）。

        调用起拒收新任务（submit/map 抛 PoolClosed）；grace_timeout
        为 None 时无限等待全部已提交任务落定，否则等到宽限期到期，
        仍未落定者（含排队的）标记 CANCELLED，排队的不再执行。

        报告：{"completed": 本次落定的任务数, "cancelled": 未完成句柄列表}。
        """
        with self._close_done:
            while self._close_report is None:
                if not self._closed:
                    self._closed = True
                    break
                # 另一个线程的首次 close 仍在等待，等它的报告落定
                self._close_done.wait()
            else:
                return self._close_report
            pending = [t for t in self._tasks if not t.done]

        deadline = None if grace_timeout is None else time.monotonic() + grace_timeout
        for task in pending:
            if task.done:
                continue
            left = None if deadline is None else max(0.0, deadline - time.monotonic())
            if not task.wait(left):
                break

        cancelled = [t for t in pending if t._cancel()]
        completed = sum(1 for t in pending if t.done and t.state != CANCELLED)
        report = CloseReport(completed=completed, cancelled=cancelled)
        with self._close_done:
            self._close_report = report
            self._close_done.notify_all()
        return report

    def _atexit_close(self):
        # 进程退出钩子：无时限等待，已显式 close 过则直接拿首次报告。
        return self.close()

    def _worker_loop(self):
        # 常驻循环：队列空就阻塞等待，线程是 daemon，不阻塞进程退出。
        # 关闭后排在队里的 CANCELLED 任务出队时由 Task._run 自行跳过。
        while True:
            task = self._queue.get()
            task._run()
