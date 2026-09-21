"""抓取队列的去重门面：标记已入队的 URL、判重、必要时撤销。"""

import struct

from .bloom import BloomFilter
from .cuckoo import CuckooFilter, fp_bits_for_rate
from .errors import NotSupportedError

MAGIC = b"DDS1"
MAGIC_CUCKOO = b"DDS2"
# magic, marks, queries, duplicates, fp_rate
_HEADER = struct.Struct(">4sQQQd")


class DedupStore:
    """门面层，构造参数透传给底层过滤器。

    mark 记下一条 URL，is_duplicate 回答它之前是否标记过，
    retry 把一条 URL 从集合里撤下来。底层是近似结构，判重会多报不会漏报。
    backend="bloom"（默认）只加不删；backend="cuckoo" 支持 retry 真删。
    """

    def __init__(self, capacity, fp_rate=0.01, backend="bloom"):
        self.capacity = int(capacity)
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        self.fp_rate = float(fp_rate)
        if not 0.0 < self.fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        self.backend = backend
        if backend == "bloom":
            self._filter = BloomFilter(self.capacity, self.fp_rate)
        elif backend == "cuckoo":
            self._filter = CuckooFilter(self.capacity, fp_bits_for_rate(self.fp_rate))
        else:
            raise ValueError("unknown backend: %r" % (backend,))
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

        布隆过滤器删不了位，这里没得商量；布谷鸟后端真删，返回是否撤到。
        """
        remove = getattr(self._filter, "remove", None)
        if remove is None:
            raise NotSupportedError("current backend cannot remove keys")
        return remove(key)

    def stats(self):
        """计数快照，独立 dict，filter 键下是底层过滤器的统计。"""
        return {
            "marks": self._marks,
            "queries": self._queries,
            "duplicates": self._duplicates,
            "backend": self.backend,
            "filter": self._filter.stats(),
        }

    def to_bytes(self):
        magic = MAGIC if self.backend == "bloom" else MAGIC_CUCKOO
        head = _HEADER.pack(magic, self._marks, self._queries, self._duplicates, self.fp_rate)
        return head + self._filter.to_bytes()

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, marks, queries, duplicates, fp_rate = _HEADER.unpack(blob[:_HEADER.size])
        if magic == MAGIC:
            backend = "bloom"
            filt = BloomFilter.from_bytes(blob[_HEADER.size:])
        elif magic == MAGIC_CUCKOO:
            backend = "cuckoo"
            filt = CuckooFilter.from_bytes(blob[_HEADER.size:])
        else:
            raise ValueError("bad magic: %r" % (magic,))
        obj = cls.__new__(cls)
        obj.backend = backend
        obj._filter = filt
        obj.capacity = obj._filter.capacity
        obj.fp_rate = fp_rate
        obj._marks = marks
        obj._queries = queries
        obj._duplicates = duplicates
        return obj
