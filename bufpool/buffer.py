"""缓冲对象。

Buffer 包着一段 bytearray。acquire(size) 拿到的缓冲，size 是请求容量，
capacity 是实际可用字节数，可能大于请求（分配器向上取整到档位）。
view() 给的是整段可写视图，调用方自己能写到 capacity 个字节。
"""


class Buffer:
    """一段可取用的连续内存。"""

    __slots__ = ("_data", "_size", "serial")

    def __init__(self, data, size, serial=0):
        if not isinstance(data, bytearray):
            raise TypeError("底层存储必须是 bytearray")
        self._data = data
        self._size = size
        self.serial = serial

    @property
    def size(self):
        """请求的容量。"""
        return self._size

    @property
    def capacity(self):
        """实际可用字节数，不小于 size。"""
        return len(self._data)

    def view(self):
        """整段可用空间的可写视图，长度等于 capacity。"""
        return memoryview(self._data)

    def zero(self):
        """把整段空间清零。"""
        self._data[:] = b"\x00" * len(self._data)

    def __len__(self):
        return self._size

    def __repr__(self):
        return "<Buffer serial=%d size=%d capacity=%d>" % (
            self.serial, self._size, self.capacity)
