"""固定大小线程池。

submit 把任务放进队列，size 个常驻工作线程逐个领取执行；
每个任务对应一个 Task 句柄，用来查状态、等落定、取结果。
"""

import queue
import threading
import time

PENDING = "pending"
RUNNING = "running"
FINISHED = "finished"
FAILED = "failed"


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
        """PENDING / RUNNING / FINISHED / FAILED 之一。"""
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
        self._state = RUNNING
        try:
            self._result = self._fn(*self._args, **self._kwargs)
        except BaseException as exc:
            self._exception = exc
            self._state = FAILED
        else:
            self._state = FINISHED
        self._done.set()


class WorkerPool:
    """固定大小线程池：size 个常驻线程共享一个任务队列。

    并发上限就是 size，多余的提交在队列里排队。
    """

    def __init__(self, size):
        if size < 1:
            raise ValueError("size must be >= 1")
        self._queue = queue.SimpleQueue()
        self._tasks = []
        self._seq = 0
        self._workers = [
            threading.Thread(target=self._worker_loop, daemon=True)
            for _ in range(size)
        ]
        for w in self._workers:
            w.start()

    @property
    def size(self):
        return len(self._workers)

    @property
    def tasks(self):
        """全部已提交任务的句柄快照，按提交顺序；外部改不了内部列表。"""
        return tuple(self._tasks)

    def submit(self, fn, *args, **kwargs):
        """提交任务，立即返回句柄，不等待执行。"""
        task = Task(fn, args, kwargs, seq=self._seq)
        self._seq += 1
        self._tasks.append(task)
        self._queue.put(task)
        return task

    def map(self, fn, *iterables):
        """批量提交，阻塞到全部完成，按提交顺序返回结果列表。"""
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

    def _worker_loop(self):
        # 常驻循环：队列空就阻塞等待，线程是 daemon，不阻塞进程退出。
        while True:
            task = self._queue.get()
            task._run()
