"""索引二叉堆：存待执行的任务记录。

弹出顺序由 HeapEntry.key 决定，优先级数字小的先出；capacity() 报告槽位数。
"""


class HeapEntry:
    """堆里的一条任务记录。"""

    __slots__ = ("prio", "task_id")

    def __init__(self, prio, task_id):
        self.prio = prio
        self.task_id = task_id

    def key(self):
        return (self.prio, self.task_id)

    def __repr__(self):
        return "HeapEntry(prio=%r, task_id=%r)" % (self.prio, self.task_id)


class IndexedHeap:
    """二叉最小堆，元素是 HeapEntry，同一个 task_id 允许多条记录。"""

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

    def push(self, prio, task_id):
        """压入一条新记录并返回它。"""
        entry = HeapEntry(prio, task_id)
        self._append(entry)
        self._sift_up(self._size - 1)
        return entry

    def restore(self, entry):
        """把一条先前取出过的记录放回堆里并返回它；占用末位即可。"""
        self._append(entry)
        return entry

    def pop_min(self):
        """取出 key 最小的记录；堆空时返回 None。"""
        if self._size == 0:
            return None
        items = self._items
        top = items[0]
        last = items[self._size - 1]
        items[self._size - 1] = None
        self._size -= 1
        if self._size:
            items[0] = last
            self._sift_down(0)
        return top

    def peek(self):
        """看一眼 key 最小的记录，不取走。"""
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
        self._size += 1

    def _sift_up(self, index):
        items = self._items
        entry = items[index]
        while index > 0:
            parent = (index - 1) // 2
            if items[parent].key() <= entry.key():
                break
            items[index] = items[parent]
            index = parent
        items[index] = entry

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
            items[index] = items[child]
            index = child
        items[index] = entry
