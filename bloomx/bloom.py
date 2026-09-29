"""定容布隆过滤器：位数组加双重哈希展开的多个下标，只加不删。"""

import struct

from .errors import NotSupportedError
from .hashing import bit_indexes, hash_pair, sizing

MAGIC = b"BXBF"
# magic, num_bits, num_hashes, capacity, fp_rate, added
_HEADER = struct.Struct(">4sIIIdQ")


class BloomFilter:
    """定容布隆过滤器。

    capacity 与 fp_rate 只在构造时用来定 num_bits 与 num_hashes，
    之后加键不再变化；contains 说不在就一定不在，说在可能没加过。
    位数组只置位不清位，删不了，remove 一律抛 NotSupportedError。
    """

    def __init__(self, capacity, fp_rate=0.01):
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

    def remove(self, key):
        """定容布隆删不了位，这里没得商量。"""
        raise NotSupportedError("BloomFilter cannot remove keys")

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

    def to_bytes(self):
        """落盘格式：定长头加位数组，头里带上构造参数与计数。"""
        head = _HEADER.pack(
            MAGIC, self.num_bits, self.num_hashes, self.capacity, self.fp_rate, self._added
        )
        return head + bytes(self._bits)

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, num_bits, num_hashes, capacity, fp_rate, added = _HEADER.unpack(
            blob[:_HEADER.size]
        )
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        bits = bytearray(blob[_HEADER.size:])
        if len(bits) != (num_bits + 7) // 8:
            raise ValueError("bit payload length mismatch")
        obj = cls.__new__(cls)
        obj.capacity = capacity
        obj.fp_rate = fp_rate
        obj.num_bits = num_bits
        obj.num_hashes = num_hashes
        obj._bits = bits
        obj._added = added
        return obj
