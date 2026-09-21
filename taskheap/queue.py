"""任务队列：提交、按优先级弹出、执行失败回滚。

任务按优先级排队，数字小的先弹出；弹出即进入执行中，成功用 done 收尾，
失败用 release 放回等下一轮。堆在 heap.py，本模块只管状态流转和对外接口。
"""

from .heap import HeapEntry, IndexedHeap

STATE_QUEUED = "queued"
STATE_RUNNING = "running"


def _check_prio(prio):
    if isinstance(prio, bool) or not isinstance(prio, int):
        raise TypeError("prio must be an int, got %r" % (prio,))
    return prio


class TaskRecord:
    """队列里一条任务的档案。"""

    __slots__ = ("task_id", "prio", "state")

    def __init__(self, task_id, prio):
        self.task_id = task_id
        self.prio = prio
        self.state = STATE_QUEUED


class TaskQueue:
    """优先级任务队列，同一时刻一个任务只应被弹出一次。"""

    def __init__(self):
        self._heap = IndexedHeap()
        self._records = {}
        self._running = {}

    def push(self, task_id, prio):
        """提交一个任务，prio 越小越先执行。"""
        if task_id in self._records:
            raise ValueError("task already in queue: %r" % (task_id,))
        _check_prio(prio)
        self._records[task_id] = TaskRecord(task_id, prio)
        self._heap.push(prio, task_id)

    def pop(self):
        """弹出下一个该执行的任务号；没有可弹的任务时返回 None。"""
        while True:
            entry = self._heap.pop_min()
            if entry is None:
                return None
            record = self._records.get(entry.task_id)
            if record is None:
                # 任务号已经不在册，这条记录没有主人，丢掉继续。
                continue
            record.state = STATE_RUNNING
            self._running[entry.task_id] = record
            return entry.task_id

    def pop_batch(self, count):
        """连续弹出至多 count 个任务，按弹出顺序返回任务号列表。"""
        batch = []
        for _ in range(count):
            task_id = self.pop()
            if task_id is None:
                break
            batch.append(task_id)
        return batch

    def done(self, task_id):
        """执行成功的任务收尾，之后不再回到队列。"""
        record = self._records.get(task_id)
        if record is None or record.state != STATE_RUNNING:
            raise KeyError(task_id)
        del self._records[task_id]
        del self._running[task_id]

    def release(self, task_id):
        """执行失败的任务放回队列，等下一轮再被弹出。"""
        record = self._records.get(task_id)
        if record is None:
            raise KeyError(task_id)
        record.state = STATE_QUEUED
        self._running.pop(task_id, None)
        self._heap.restore(HeapEntry(record.prio, task_id))

    def update_priority(self, task_id, prio):
        """调整一个任务的优先级，随后按新优先级参与排队。"""
        _check_prio(prio)
        record = self._records.get(task_id)
        if record is None:
            raise KeyError(task_id)
        self._heap.push(prio, task_id)
        record.prio = prio

    def pending(self):
        """排队中的任务号，按下一轮弹出的顺序排列。"""
        entries = sorted(self._heap.live_entries(), key=lambda entry: entry.key())
        return [entry.task_id for entry in entries]

    def running(self):
        """执行中的任务号，按弹出顺序。"""
        return list(self._running)

    def queued(self, task_id):
        """这个任务是不是正排着队等弹出。"""
        record = self._records.get(task_id)
        return record is not None and record.state == STATE_QUEUED

    def size(self):
        """排队中的记录数，不含执行中的任务。"""
        return self._heap.size()

    def capacity(self):
        """后备存储的槽位数，给内存观察用。"""
        return self._heap.capacity()
