"""排序列表参考实现：语义与 TaskQueue 对齐，用来做行为对照。

每条记录带提交序号，排队记录按 (优先级, 提交序号) 排好放在一张表里，执行中
的另放一张表；查找、回滚、收尾都从头扫，怎么直白怎么写，元素一多就慢，
只适合小规模对照和测试，别拿去跑线上流量。
"""

import bisect

STATE_QUEUED = "queued"
STATE_RUNNING = "running"


def _check_prio(prio):
    if isinstance(prio, bool) or not isinstance(prio, int):
        raise TypeError("prio must be an int, got %r" % (prio,))
    return prio


class _Record:
    """参考实现里的任务档案，seq 是提交序号，入队时定下就不再改。"""

    __slots__ = ("task_id", "prio", "seq", "state")

    def __init__(self, task_id, prio, seq):
        self.task_id = task_id
        self.prio = prio
        self.seq = seq
        self.state = STATE_QUEUED

    @property
    def rank(self):
        return (self.prio, self.seq)


class SortedListQueue:
    """按 (优先级, 提交序号) 排队的参考实现。"""

    def __init__(self):
        self._items = []
        self._running = []
        self._next_seq = 1

    def push(self, task_id, prio):
        """提交一个任务，同优先级之间按提交先后排。"""
        table, _, _ = self._locate(task_id)
        if table is not None:
            raise ValueError("task already in queue: %r" % (task_id,))
        _check_prio(prio)
        record = _Record(task_id, prio, self._next_seq)
        self._next_seq += 1
        self._place(record)

    def pop(self):
        """弹出下一个该执行的任务号；没有可弹的任务时返回 None。"""
        if not self._items:
            return None
        record = self._items.pop(0)
        record.state = STATE_RUNNING
        self._running.append(record)
        return record.task_id

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
        table, index, _ = self._locate(task_id)
        if table is not self._running:
            raise KeyError(task_id)
        del table[index]

    def release(self, task_id):
        """执行失败的任务放回队列，回到它原来该在的位置。"""
        table, index, record = self._locate(task_id)
        if table is not self._running:
            raise KeyError(task_id)
        del table[index]
        record.state = STATE_QUEUED
        self._place(record)

    def update_priority(self, task_id, prio):
        """调整一个排队中任务的优先级，提交序号不动。"""
        _check_prio(prio)
        table, index, record = self._locate(task_id)
        if table is not self._items:
            raise KeyError(task_id)
        if record.prio == prio:
            return
        del table[index]
        record.prio = prio
        self._place(record)

    def pending(self):
        """排队中的任务号，按下一轮弹出的顺序排列。"""
        return [record.task_id for record in self._items]

    def running(self):
        """执行中的任务号，按弹出顺序。"""
        return [record.task_id for record in self._running]

    def queued(self, task_id):
        """这个任务是不是正排着队等弹出。"""
        table, _, _ = self._locate(task_id)
        return table is self._items

    def size(self):
        """排队中的任务数，不含执行中的任务。"""
        return len(self._items)

    def capacity(self):
        """存储层指标，参考实现里就是元素个数。"""
        return len(self._items)

    def _locate(self, task_id):
        """按任务号找记录，返回它所在的表、下标和记录本身。"""
        for index, record in enumerate(self._items):
            if record.task_id == task_id:
                return self._items, index, record
        for index, record in enumerate(self._running):
            if record.task_id == task_id:
                return self._running, index, record
        return None, -1, None

    def _place(self, record):
        bisect.insort(self._items, record, key=lambda item: item.rank)
