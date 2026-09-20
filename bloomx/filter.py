"""固定容量的布隆过滤器：按容量与目标假阳性率算位数组大小。"""
import hashlib
import math
import struct

MAGIC = b"BLM1"
_HEADER = struct.Struct(">4sIIQ")  # magic, num_bits, num_hashes, count
_SALT = b"bloomx"


class BloomFilter:
    """单实例定容布隆过滤器。add 用双重哈希置位，查询只看位数组。"""

    def __init__(self, capacity, fp_rate=0.01):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0.0 < fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        self.capacity = int(capacity)
        self.fp_rate = float(fp_rate)
        self.num_bits = self._bits_for(self.capacity, self.fp_rate)
        self.num_hashes = self._hashes_for(self.num_bits, self.capacity)
        self._bits = bytearray((self.num_bits + 7) // 8)
        self._count = 0

    @staticmethod
    def _bits_for(n, p):
        m = -(n * math.log(p)) / (math.log(2) ** 2)
        return max(8, int(math.ceil(m)))

    @staticmethod
    def _hashes_for(m, n):
        return max(1, int(round((m / n) * math.log(2))))

    def _indexes(self, item):
        raw = item if isinstance(item, (bytes, bytearray)) else str(item).encode("utf-8")
        digest = hashlib.sha256(_SALT + bytes(raw)).digest()
        h1 = int.from_bytes(digest[:16], "big")
        h2 = int.from_bytes(digest[16:], "big")
        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.num_bits

    def add(self, item):
        for idx in self._indexes(item):
            self._bits[idx >> 3] |= 1 << (idx & 7)
        self._count += 1

    def __contains__(self, item):
        for idx in self._indexes(item):
            if not (self._bits[idx >> 3] >> (idx & 7)) & 1:
                return False
        return True

    def __len__(self):
        return self._count

    def to_bytes(self):
        header = _HEADER.pack(MAGIC, self.num_bits, self.num_hashes, self._count)
        return header + bytes(self._bits)

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, num_bits, num_hashes, count = _HEADER.unpack(blob[: _HEADER.size])
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        bits = bytearray(blob[_HEADER.size:])
        if len(bits) != (num_bits + 7) // 8:
            raise ValueError("bit payload length mismatch")
        obj = cls.__new__(cls)
        obj.capacity = 0
        obj.fp_rate = 0.0
        obj.num_bits = num_bits
        obj.num_hashes = num_hashes
        obj._bits = bits
        obj._count = count
        return obj
