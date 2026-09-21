"""索引二叉堆：存待执行的任务记录。

弹出顺序由 HeapEntry.key 决定，优先级数字小的先出；key 里带提交序号时，
同优先级按提交先后走。每条记录记住自己在后备数组里的下标，支持原地改
优先级和放回；capacity() 报告槽位数，排空后槽位全部释放。
"""

# 后备数组缩容的门槛：元素数低于容量四分之一、且容量超过这个值时缩一半。
_SHRINK_CAPACITY = 8


class HeapEntry:
    """堆里的一条任务记录。"""

    __slots__ = ("prio", "task_id", "seq", "index")

    def __init__(self, prio, task_id, seq=None):
        self.prio = prio
        self.task_id = task_id
        # seq 是提交序号，定下就不再变；不给序号时退回用任务号比先后，
        # 兼容直接操作 IndexedHeap 的老用法。
        self.seq = task_id if seq is None else seq
        self.index = -1

    def key(self):
        return (self.prio, self.seq)

    def __repr__(self):
        return "HeapEntry(prio=%r, task_id=%r, seq=%r)" % (
            self.prio, self.task_id, self.seq)


class IndexedHeap:
    """二叉最小堆，元素是 HeapEntry，每条记录记住自己的下标。"""

    def __init__(self):
        self._items = []
        self._size = 0

    def __len__(self):
        return self._size

    def size(self):
        """堆里当前的记录条数。"""
        return self._size

    def capacity(self):
        """后备存储占用的槽位数。"""
        return len(self._items)

    def push(self, prio, task_id, seq=None):
        """压入一条新记录并返回它，seq 决定同优先级时的先后。"""
        return self.restore(HeapEntry(prio, task_id, seq))

    def restore(self, entry):
        """把一条先前取出过的记录放回堆里并返回它，保留原优先级和序号。"""
        self._attach(entry, self._size)
        self._sift_up(entry.index)
        return entry

    def change_priority(self, entry, prio):
        """原地改一条记录的优先级，提交序号不动。"""
        old_prio = entry.prio
        entry.prio = prio
        index = entry.index
        if prio < old_prio:
            self._sift_up(index)
        elif prio > old_prio:
            self._sift_down(index)
        return entry

    def pop_min(self):
        """取出 key 最小的记录；堆空时返回 None。"""
        if self._size == 0:
            return None
        items = self._items
        top = items[0]
        top.index = -1
        self._size -= 1
        if self._size:
            last = items[self._size]
            items[self._size] = None
            self._place(last, 0)
            self._sift_down(0)
        else:
            items[0] = None
        self._shrink_if_needed()
        return top

    def peek(self):
        """看一眼 key 最小的记录，不取走。"""
        if self._size == 0:
            return None
        return self._items[0]

    def live_entries(self):
        """按堆序返回当前全部记录，调试和快照用。"""
        return self._items[:self._size]

    def _attach(self, entry, index):
        """把记录放进指定槽位并登记下标，必要时先扩容。"""
        if self._size == len(self._items):
            self._items.append(None)
        self._items[index] = entry
        entry.index = index
        self._size += 1

    def _place(self, entry, index):
        """把已在册的记录移到指定槽位，并同步登记下标。"""
        self._items[index] = entry
        entry.index = index

    def _shrink_if_needed(self):
        """元素数明显少于槽位数时缩回，保证容量跟元素数同量级。"""
        capacity = len(self._items)
        if capacity > _SHRINK_CAPACITY and self._size * 4 <= capacity:
            del self._items[self._size:]
        elif self._size == 0:
            self._items = []

    def _sift_up(self, index):
        items = self._items
        entry = items[index]
        while index > 0:
            parent = (index - 1) // 2
            if items[parent].key() <= entry.key():
                break
            self._place(items[parent], index)
            index = parent
        self._place(entry, index)

    def _sift_down(self, index):
        items = self._items
        size = self._size
        entry = items[index]
        while True:
            child = 2 * index + 1
            if child >= size:
                break
            right = child + 1
            if right < size and items[right].key() < items[child].key():
                child = right
            if entry.key() <= items[child].key():
                break
            self._place(items[child], index)
            index = child
        self._place(entry, index)
