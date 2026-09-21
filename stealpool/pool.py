"""固定线程池加全局队列的调度器，附带运行统计。"""

import os
import queue
import threading
import time

from stealpool.errors import PoolClosed
from stealpool.future import Future

# 关闭池时往队列里放的路标，worker 取到就退出
_STOP = object()


class Stats:
    """池的运行统计。

    busy / idle / tasks 按 worker 分槽，看负载匀不匀靠它们。
    """

    def __init__(self, workers):
        self._lock = threading.Lock()
        self._workers = workers
        self._submitted = self._completed = self._failed = self._steals = 0
        self._busy = [0.0] * workers
        self._idle = [0.0] * workers
        self._tasks = [0] * workers

    def submitted(self, n=1):
        with self._lock:
            self._submitted += n

    def steal(self, n=1):
        """记 n 次从别的 worker 那里取走任务。"""
        with self._lock:
            self._steals += n

    def flush(self, index, busy=0.0, idle=0.0, tasks=0, failed=0):
        """worker 把本地累计值刷进自己的槽位。

        tasks 是本批跑完的条数（含失败的），completed 只记成功的那部分。
        """
        with self._lock:
            self._busy[index] += busy
            self._idle[index] += idle
            self._tasks[index] += tasks
            self._completed += tasks - failed
            self._failed += failed

    def snapshot(self):
        with self._lock:
            return dict(
                workers=self._workers, submitted=self._submitted,
                completed=self._completed, failed=self._failed, steals=self._steals,
                busy_seconds=list(self._busy), idle_seconds=list(self._idle),
                tasks=list(self._tasks),
            )


class Pool:
    """固定线程数的任务池。

    提交的任务统一进全局队列，哪个 worker 空闲哪个来取，
    和提交它的线程没有绑定关系。
    """

    def __init__(self, workers=None, name="stealpool"):
        if workers is None:
            workers = os.cpu_count() or 1
        if workers < 1:
            raise ValueError("workers 至少为 1")
        self._worker_count = workers
        self._name = name
        self._queue = queue.Queue()
        self._stats = Stats(workers)
        self._lock = threading.Lock()
        self._closed = False
        self._threads = []
        for index in range(workers):
            thread = threading.Thread(target=self._worker_main, args=(index,),
                                      name="%s-%d" % (name, index), daemon=True)
            thread.start()
            self._threads.append(thread)

    @property
    def workers(self):
        """线程数。"""
        return self._worker_count

    def submit(self, fn, *args, **kwargs):
        """提交一个任务，返回 Future。"""
        future = Future()
        with self._lock:
            if self._closed:
                raise PoolClosed("池已关闭，不能再提交任务")
            self._stats.submitted()
            self._queue.put((future, fn, args, kwargs))
        return future

    def shutdown(self, wait=True):
        """关闭池；wait 为真时等所有 worker 退出。可重复调用。"""
        with self._lock:
            first = not self._closed
            self._closed = True
        if first:
            for _ in range(self._worker_count):
                self._queue.put(_STOP)
        if wait:
            for thread in self._threads:
                thread.join()

    def stats(self):
        """返回统计快照（含每 worker 的忙碌与空闲秒数）。"""
        return self._stats.snapshot()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.shutdown()

    # 内部实现 ----------------------------------------------------------

    def _worker_main(self, index):
        busy = idle = 0.0
        tasks = failed = 0
        while True:
            # 取下一个任务之前，把上一轮的本地累计刷进统计
            self._stats.flush(index, busy=busy, idle=idle, tasks=tasks, failed=failed)
            busy = idle = 0.0
            tasks = failed = 0
            waiting = time.monotonic()
            item = self._queue.get()
            idle += time.monotonic() - waiting
            if item is _STOP:
                self._stats.flush(index, idle=idle)
                break
            future, fn, args, kwargs = item
            if not future.set_running_or_notify_cancel():
                continue
            started = time.monotonic()
            try:
                value = fn(*args, **kwargs)
            except Exception as exc:
                tasks += 1
                failed += 1
                future.set_exception(exc)
            else:
                tasks += 1
                future.set_result(value)
            busy += time.monotonic() - started
