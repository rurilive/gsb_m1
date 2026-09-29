"""大块分配器：从一块容量里按请求大小切出定长块。

当前是最朴素的实现 BumpAlloc：一个一进一出的大块分配器。分配就从
可用区末尾切一块出来，偏移顺次往后推；释放是空操作，块直接浪费，
没有空闲表，没有复用，没有相邻合并，也没有任何碎片管理。
"""


class HeapError(Exception):
    """chunkheap 的异常基类：所有自定义异常都从这里派生。"""


class AllocError(HeapError):
    """非法请求或非法状态。"""


class BumpAlloc:
    """一进一出的大块分配器。

    capacity: 总容量字节数。
    分配返回块起始偏移，块首带一个头部（记录大小与占用标记），请求
    返回的是头部之后的数据偏移。释放是空操作，只把头部标记为非占用，
    不回收、不复用，容量只减不增。
    """

    HEADER = 16

    def __init__(self, capacity):
        if capacity < 0:
            raise AllocError("capacity must be non-negative")
        self._capacity = capacity
        self._next = 0
        self._last_data = None

    @property
    def capacity(self):
        """总容量字节数。"""
        return self._capacity

    @property
    def used(self):
        """已切出的字节数，含头部开销。"""
        return self._next

    def alloc(self, size):
        """从末尾切出一块，返回数据偏移。

        需要的空间是头部加上请求字节数。装不下就报错，不做任何回收。
        """
        if size < 0:
            raise AllocError("size must be non-negative")
        need = self.HEADER + size
        if self._next + need > self._capacity:
            raise AllocError("out of capacity")
        start = self._next
        self._next += need
        data = start + self.HEADER
        self._last_data = data
        return data

    def free(self, offset):
        """释放：空操作，不回收也不复用。"""
        return None

    def message(self):
        """一句人类可读的现状说明。"""
        return "bump allocator, next=%d of %d" % (self._next, self._capacity)
