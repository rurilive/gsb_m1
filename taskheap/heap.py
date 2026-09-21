"""索引二叉堆：存待执行的任务记录。

堆里同一个 task_id 至多一条记录，_index 记住每条记录的槽位，支持按任务号
摘除和放回。弹出顺序由 HeapEntry.rank 决定：优先级数字小的先出，同优先级
按提交序号先来后到。capacity() 报告槽位数，后备存储随元素减少自动收缩。
"""


class HeapEntry:
    """堆里的一条任务记录，seq 是提交序号，入队时定下就不再改。"""

    __slots__ = ("prio", "task_id", "seq")

    def __init__(self, prio, task_id, seq=None):
        self.prio = prio
        self.task_id = task_id
        self.seq = seq

    def key(self):
        return (self.prio, self.task_id)

    def rank(self):
        """堆序依据：先比优先级，再比提交序号。"""
        return (self.prio, self.seq)

    def __repr__(self):
        return "HeapEntry(prio=%r, task_id=%r, seq=%r)" % (
            self.prio, self.task_id, self.seq)


class IndexedHeap:
    """二叉最小堆，元素是 HeapEntry，同一个 task_id 至多一条记录。"""

    _SHRINK_THRESHOLD = 64

    def __init__(self):
        self._items = []
        self._index = {}
        self._size = 0
        self._next_seq = 0

    def __len__(self):
        return self._size

    def size(self):
        """堆里当前的记录条数。"""
        return self._size

    def capacity(self):
        """后备存储占用的槽位数。"""
        return len(self._items)

    def push(self, prio, task_id, seq=None):
        """压入一条新记录并返回它；seq 缺省时由堆内自增序号补上。"""
        if task_id in self._index:
            raise ValueError("task already in heap: %r" % (task_id,))
        if seq is None:
            seq = self._next_seq
            self._next_seq += 1
        entry = HeapEntry(prio, task_id, seq)
        self._append(entry)
        self._sift_up(self._size - 1)
        return entry

    def restore(self, entry):
        """把一条先前取出过的记录放回堆里，按堆序归位后返回它。"""
        if entry.task_id in self._index:
            raise ValueError("task already in heap: %r" % (entry.task_id,))
        self._append(entry)
        self._sift_up(self._size - 1)
        return entry

    def remove(self, task_id):
        """按任务号摘除一条记录并返回它；不在堆里时抛 KeyError。"""
        index = self._index[task_id]
        return self._remove_at(index)

    def pop_min(self):
        """取出 rank 最小的记录；堆空时返回 None。"""
        if self._size == 0:
            return None
        return self._remove_at(0)

    def peek(self):
        """看一眼 rank 最小的记录，不取走。"""
        if self._size == 0:
            return None
        return self._items[0]

    def live_entries(self):
        """按堆序返回当前全部记录，调试和快照用。"""
        return self._items[:self._size]

    def _append(self, entry):
        if self._size == len(self._items):
            self._items.append(entry)
        else:
            self._items[self._size] = entry
        self._index[entry.task_id] = self._size
        self._size += 1

    def _remove_at(self, index):
        items = self._items
        entry = items[index]
        last = items[self._size - 1]
        items[self._size - 1] = None
        self._size -= 1
        del self._index[entry.task_id]
        if index < self._size:
            items[index] = last
            self._index[last.task_id] = index
            if self._sift_up(index) == index:
                self._sift_down(index)
        self._maybe_shrink()
        return entry

    def _maybe_shrink(self):
        if self._size == 0:
            if self._items:
                del self._items[:]
        elif (self._size * 4 <= len(self._items)
              and len(self._items) >= self._SHRINK_THRESHOLD):
            del self._items[self._size:]

    def _sift_up(self, index):
        items = self._items
        positions = self._index
        entry = items[index]
        rank = entry.rank()
        while index > 0:
            parent = (index - 1) // 2
            parent_entry = items[parent]
            if parent_entry.rank() <= rank:
                break
            items[index] = parent_entry
            positions[parent_entry.task_id] = index
            index = parent
        items[index] = entry
        positions[entry.task_id] = index
        return index

    def _sift_down(self, index):
        items = self._items
        positions = self._index
        size = self._size
        entry = items[index]
        rank = entry.rank()
        while True:
            child = 2 * index + 1
            if child >= size:
                break
            right = child + 1
            if right < size and items[right].rank() < items[child].rank():
                child = right
            child_entry = items[child]
            if rank <= child_entry.rank():
                break
            items[index] = child_entry
            positions[child_entry.task_id] = index
            index = child
        items[index] = entry
        positions[entry.task_id] = index
        return index
