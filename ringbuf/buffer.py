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
            overwrite = self._count == self._capacity
            if overwrite:
                # 覆盖最老元素：head 与 tail 同步前移，元素个数不变
                self._head = self._advance(self._head)
            self._buf[self._tail] = item
            self._tail = self._advance(self._tail)
            if not overwrite:
                self._count += 1

    def get(self):
        """取出最老元素；缓冲为空时抛 Empty。"""
        with self._lock:
            if self._count == 0:
                raise Empty()
            item = self._buf[self._head]
            self._buf[self._head] = None
            self._head = self._advance(self._head)
            self._count -= 1
            return item

    def _advance(self, cursor):
        """游标前进一格，游标取值范围为 [0, capacity]（共 capacity+1 个槽位）。"""
        cursor += 1
        if cursor > self._capacity:
            cursor = 0
        return cursor

    def count(self):
        """当前元素个数。"""
        with self._lock:
            return self._count

    def snapshot(self):
        """导出当前内容副本，不影响缓冲状态。"""
        with self._lock:
            # 按逻辑顺序（从 head 起）导出，而非物理槽位顺序；
            # head 可能已回绕到尾部，需要跨末尾拼接。
            end = self._head + self._count
            if end <= self._capacity + 1:
                return self._buf[self._head:end]
            head_part = self._buf[self._head:]
            wrapped = end % (self._capacity + 1)
            return head_part + self._buf[:wrapped]
