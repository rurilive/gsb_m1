"""改造前的朴素布隆过滤器：一层定长位数组，只加不删。

位数组在构造时按 capacity 与 fp_rate 定死，之后不再变化。add 置位，
contains 判位，命中判定精确、不产生假阴性，但同一层写满就再没弹性，
也没法删、没法估基数、没法落盘读回。这是可扩展布隆落地前的基线实现。
"""

from .hashing import bit_indexes, hash_pair, sizing


class NaiveBloomFilter:
    """一层定长位数组的朴素布隆过滤器。

    capacity 与 fp_rate 只在构造时用来定 num_bits 与 num_hashes，之后
    加键不改这两项。contains 说不存在一定没加过，说存在可能没加过。
    位数组只置位不清位，删不了；单层装不下也只能硬撑。
    """

    def __init__(self, capacity=1024, fp_rate=0.01):
        self.num_bits, self.num_hashes = sizing(capacity, fp_rate)
        self.capacity = int(capacity)
        self.fp_rate = float(fp_rate)
        self._bits = bytearray((self.num_bits + 7) // 8)
        self._added = 0

    def add(self, key):
        """置位。同一个键重复加就是重复置位，计数照加。"""
        h1, h2 = hash_pair(key)
        for idx in bit_indexes(h1, h2, self.num_hashes, self.num_bits):
            self._bits[idx >> 3] |= 1 << (idx & 7)
        self._added += 1

    def __contains__(self, key):
        h1, h2 = hash_pair(key)
        for idx in bit_indexes(h1, h2, self.num_hashes, self.num_bits):
            if not (self._bits[idx >> 3] >> (idx & 7)) & 1:
                return False
        return True

    def contains(self, key):
        """contains 的方法形式，等同 in。"""
        return key in self

    def __len__(self):
        return self._added

    def stats(self):
        """计数快照，独立 dict。"""
        return {
            "added": self._added,
            "capacity": self.capacity,
            "num_bits": self.num_bits,
            "num_hashes": self.num_hashes,
            "size_bytes": len(self._bits),
        }
