"""定长环形缓冲：满时覆盖最老元素，读写线程安全。"""

import threading


class Empty(Exception):
    """缓冲为空时 get 抛出。"""


class RingBuffer:
    """多生产者/多消费者定长环形缓冲。

    - put 永不阻塞，缓冲满时覆盖最老元素
    - get 在缓冲为空时抛 Empty
    - count / snapshot 用于观测与排障
    """

    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity 必须为正整数")
        self._capacity = capacity
        # 槽位比容量多留一格，游标回绕不依赖取模
        self._buf = [None] * (capacity + 1)
        self._head = 0
        self._tail = 0
        self._count = 0
        self._lock = threading.Lock()

    def put(self, item):
        """写入一个元素；缓冲已满时淘汰最老元素。"""
        with self._lock:
            if self._count == self._capacity:
                self._advance_head()
            self._buf[self._tail] = item
            self._tail += 1
            if self._tail > self._capacity:
                self._tail = 0
            self._count += 1

    def get(self):
        """取出最老元素；缓冲为空时抛 Empty。"""
        with self._lock:
            if self._count == 0:
                raise Empty()
            item = self._buf[self._head]
        self._advance_head()
        self._count -= 1
        return item

    def _advance_head(self):
        """读游标前进一格。"""
        self._head += 1
        if self._head >= self._capacity:
            self._head = 0

    def count(self):
        """当前元素个数。"""
        with self._lock:
            return self._count

    def snapshot(self):
        """导出当前内容副本，不影响缓冲状态。"""
        with self._lock:
            return list(self._buf)[:self._count]
