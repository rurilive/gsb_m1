"""朴素的先进先出任务队列。

FifoQueue 只做一件事：把任务按入队的先后顺序存起来，再按同样的顺序取出。
任务体本身不做任何校验或变换，入队时是什么、出队时还是什么。
"""

from collections import deque


class FifoQueue:
    """先入先出的无界任务队列。"""

    def __init__(self):
        self._items = deque()

    def push(self, task):
        """把一个任务放到队尾，返回任务本身。"""
        if task is None:
            raise ValueError("task 不能是 None")
        self._items.append(task)
        return task

    def pop(self):
        """从队首取出一个任务；队列为空时返回 None。"""
        if not self._items:
            return None
        return self._items.popleft()

    def peek(self):
        """看一眼队首任务但不取走；队列为空时返回 None。"""
        if not self._items:
            return None
        return self._items[0]

    def __len__(self):
        return len(self._items)

    def __bool__(self):
        return bool(self._items)
