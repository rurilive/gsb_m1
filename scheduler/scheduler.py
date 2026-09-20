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
        self._lock = threading.RLock()
        self._stopping = False
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []
        self._epoch = 0

    # ---- 对外 API ------------------------------------------------------------
    def add(self, task_id: str, trigger: Trigger, fn, paused: bool = False) -> None:
        with self._lock:
            if task_id in self._tasks:
                raise ValueError(f"task 已存在: {task_id}")
            nxt = trigger.next_after(self._clock.now())
            task = Task(task_id, trigger, fn, nxt, paused)
            task.generation = self._next_gen()
            self._tasks[task_id] = task

    def remove(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.pop(task_id, None)
            if task is not None:
                task.generation = self._next_gen()

    def pause(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.paused = True
            task.generation = self._next_gen()

    def resume(self, task_id: str) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            task.paused = False
            if task.next_run <= self._clock.now():
                # 暂停期间错过的槽位不补跑：恢复时从当前时刻重新排程。
                task.next_run = task.trigger.next_after(self._clock.now())
            task.generation = self._next_gen()

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def start(self) -> None:
        with self._lock:
            self._stopping = False
            self._stop_event = threading.Event()
            self._inflight.clear()
            threads = [threading.Thread(target=self._loop, name="gsb-sched-loop", daemon=True)]
            for i in range(self._worker_count):
                threads.append(threading.Thread(target=self._worker,
                                                name=f"gsb-worker-{i}", daemon=True))
            self._threads = threads
        for thread in threads:
            thread.start()

    def stop(self) -> None:
        self._stopping = True
        self._stop_event.set()
        wake = getattr(self._clock, "interrupt", None)
        if callable(wake):
            wake()
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads = []

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """等待队列清空且无在途任务（真实时间轮询，仅用于测试等待）。

        需要连续两次观测到空闲，避免 loop 尚未入队的瞬间被误判为空闲。
        """
        deadline = _time.time() + timeout
        confirmed = False
        while _time.time() < deadline:
            with self._lock:
                idle = self._queue.empty() and not self._inflight
            if idle and confirmed:
                return True
            confirmed = idle
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
            for task in self._tasks.values():
                task.generation = self._next_gen()

    # ---- 内部 -----------------------------------------------------------------
    def _next_gen(self) -> int:
        self._epoch += 1
        return self._epoch

    def _loop(self) -> None:
        while not self._stopping:
            now = self._clock.now()
            with self._lock:
                for task in list(self._tasks.values()):
                    if task.paused or task.id in self._inflight:
                        continue
                    if task.next_run > now:
                        continue
                    late = (now - task.next_run).total_seconds()
                    while task.next_run <= now:
                        task.next_run = task.trigger.next_after(task.next_run)
                    # 注意：late <= grace 才补跑，且每次扫描最多入队一次。
                    # 超过宽限期的触发点视为 misfire 直接丢弃，只把 next_run
                    # 推进到未来，避免时钟前跳后逐格疯狂补跑。
                    if late <= self._misfire_grace:
                        self._inflight.add(task.id)
                        self._queue.put((task.id, task.generation))
            if self._stopping or self._clock.wait(self._tick, self._stop_event):
                self._stopping = True

    def _worker(self) -> None:
        while not self._stopping:
            try:
                task_id, _gen = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            fn = None
            with self._lock:
                task = self._tasks.get(task_id)
                if task is not None and task.generation == _gen and not task.paused:
                    fn = task.fn
            if fn is not None:
                try:
                    fn()
                finally:
                    with self._lock:
                        self._inflight.discard(task_id)
                continue
            with self._lock:
                self._inflight.discard(task_id)
