"""调度器主体：到期收集、misfire 控制、worker 池、增删暂停恢复。"""
import queue
import threading
import time as _time
from datetime import datetime

from .clock import Clock, SystemClock
from .store import Store
from .triggers import Trigger


class Task:
    __slots__ = ("id", "trigger", "fn", "next_run", "paused", "generation")

    def __init__(self, task_id: str, trigger: Trigger, fn, next_run: datetime, paused: bool = False):
        self.id = task_id
        self.trigger = trigger
        self.fn = fn
        self.next_run = next_run
        self.paused = paused
        self.generation = 0


class Scheduler:

    def __init__(self, clock: Clock | None = None, worker_count: int = 2,
                 tick: float = 1.0, misfire_grace: float = 60.0, store: Store | None = None):
        self._clock = clock or SystemClock()
        self._worker_count = worker_count
        self._tick = tick
        self._misfire_grace = misfire_grace
        self._store = store or Store()
        self._tasks: dict[str, Task] = {}
        self._inflight: set[str] = set()
        self._queue: "queue.Queue[tuple[str, int]]" = queue.Queue()
        self._gen_seq = 0
        self._lock = threading.RLock()
        self._stopping = False
        self._threads: list[threading.Thread] = []

    # ---- 对外 API ------------------------------------------------------------
    def add(self, task_id: str, trigger: Trigger, fn, paused: bool = False) -> None:
        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"task 已存在: {task_id}")
            nxt = trigger.next_after(self._clock.now())
            task = Task(task_id, trigger, fn, nxt, paused)
            self._gen_seq += 1
            task.generation = self._gen_seq
            self._tasks[task_id] = task

    def remove(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)
            self._inflight.discard(task_id)

    def pause(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.paused = True
            self._gen_seq += 1
            task.generation = self._gen_seq

    def resume(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.paused = False
            self._gen_seq += 1
            task.generation = self._gen_seq

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def start(self) -> None:
        self._stopping = False
        t = threading.Thread(target=self._loop, name="gsb-sched-loop", daemon=True)
        t.start()
        self._threads = [t]
        for i in range(self._worker_count):
            w = threading.Thread(target=self._worker, name=f"gsb-worker-{i}", daemon=True)
            w.start()
            self._threads.append(w)

    def stop(self) -> None:
        self._stopping = True

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """等待队列清空且无在途任务（真实时间轮询，仅用于测试等待）。"""
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            with self._lock:
                idle = self._queue.empty() and not self._inflight
            if idle:
                return True
            _time.sleep(0.01)
        return False

    def wait_queue_len(self, n: int, timeout: float = 5.0) -> bool:
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            if self._queue.qsize() >= n:
                return True
            _time.sleep(0.01)
        return False

    # ---- 持久化委托 -----------------------------------------------------------
    def save(self, path: str) -> None:
        with self._lock:
            self._store.save(path, self._tasks)

    def load(self, path: str) -> None:
        with self._lock:
            self._tasks = self._store.load(path)

    # ---- 内部 -----------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stopping:
            now = self._clock.now()
            with self._lock:
                for task in list(self._tasks.values()):
                    if task.paused or task.id in self._inflight:
                        continue
                    if task.next_run <= now:
                        late = (now - task.next_run).total_seconds()
                        if late < self._misfire_grace:
                            self._inflight.add(task.id)
                            self._queue.put((task.id, task.generation))
                        task.next_run = task.trigger.next_after(now)
            self._clock.sleep(self._tick)

    def _worker(self) -> None:
        while not self._stopping:
            try:
                task_id, gen = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            with self._lock:
                task = self._tasks.get(task_id)
                self._inflight.discard(task_id)
                if task is None or task.paused or task.generation != gen:
                    continue
                fn = task.fn
            fn()
