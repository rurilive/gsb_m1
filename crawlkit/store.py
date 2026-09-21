"""抓取队列的去重门面：标记已入队的 URL、判重、必要时撤销。"""

import struct

from .bloom import BloomFilter
from .errors import NotSupportedError

MAGIC = b"DDS1"
# magic, marks, queries, duplicates, fp_rate
_HEADER = struct.Struct(">4sQQQd")


class DedupStore:
    """门面层，构造参数透传给底层过滤器。

    mark 记下一条 URL，is_duplicate 回答它之前是否标记过，
    retry 把一条 URL 从集合里撤下来。底层是近似结构，判重会多报不会漏报。
    """

    def __init__(self, capacity, fp_rate=0.01):
        self.capacity = int(capacity)
        self.fp_rate = float(fp_rate)
        self._filter = BloomFilter(self.capacity, self.fp_rate)
        self._marks = 0
        self._queries = 0
        self._duplicates = 0

    def mark(self, key):
        """记下一条已入队的 URL。"""
        self._filter.add(key)
        self._marks += 1

    def is_duplicate(self, key):
        """这条 URL 之前标记过吗。"""
        self._queries += 1
        if key in self._filter:
            self._duplicates += 1
            return True
        return False

    def retry(self, key):
        """把一条 URL 从去重集合里撤下来，让重试的抓取不再被判成重复。

        布隆过滤器删不了位，这里没得商量。
        """
        raise NotSupportedError("current backend cannot remove keys")

    def stats(self):
        """计数快照，独立 dict，filter 键下是底层过滤器的统计。"""
        return {
            "marks": self._marks,
            "queries": self._queries,
            "duplicates": self._duplicates,
            "filter": self._filter.stats(),
        }

    def to_bytes(self):
        head = _HEADER.pack(MAGIC, self._marks, self._queries, self._duplicates, self.fp_rate)
        return head + self._filter.to_bytes()

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, marks, queries, duplicates, fp_rate = _HEADER.unpack(blob[:_HEADER.size])
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        obj = cls.__new__(cls)
        obj._filter = BloomFilter.from_bytes(blob[_HEADER.size:])
        obj.capacity = obj._filter.capacity
        obj.fp_rate = fp_rate
        obj._marks = marks
        obj._queries = queries
        obj._duplicates = duplicates
        return obj
