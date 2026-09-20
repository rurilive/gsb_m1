"""可扩容布隆过滤器：写满当前片就在线追加新片，旧片只读，整体假阳性率有界。"""
import math
import struct
import threading

from .filter import MAGIC as LEGACY_MAGIC
from .filter import BloomFilter

MAGIC = b"BLM2"
_HEADER = struct.Struct(">4sQdIdI")  # magic, initial_capacity, fp_rate, growth, ratio, max_shards
_SHARD_META = struct.Struct(">QdI")  # capacity, fp_rate, blob length


class _Shard:
    __slots__ = ("bf", "capacity", "fp")

    def __init__(self, bf, capacity, fp):
        self.bf = bf
        self.capacity = capacity
        self.fp = fp


class ScalableBloomFilter:
    """分片可增长的布隆过滤器。只写最后一片，写满即添新片，旧片不再改动。"""

    def __init__(self, initial_capacity=1000, fp_rate=0.01, growth=2, ratio=0.9, max_shards=32):
        if initial_capacity <= 0:
            raise ValueError("initial_capacity must be positive")
        if not 0.0 < fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        if growth < 1:
            raise ValueError("growth must be >= 1")
        if not 0.0 < ratio < 1.0:
            raise ValueError("ratio must be in (0, 1)")
        if max_shards < 1:
            raise ValueError("max_shards must be >= 1")
        self.initial_capacity = int(initial_capacity)
        self.fp_rate = float(fp_rate)
        self.growth = int(growth)
        self.ratio = float(ratio)
        self.max_shards = int(max_shards)
        self._lock = threading.Lock()
        self._shards = [self._new_shard(self.initial_capacity, self.fp_rate * (1.0 - self.ratio))]

    @staticmethod
    def _new_shard(capacity, fp):
        return _Shard(BloomFilter(capacity=capacity, fp_rate=fp), int(capacity), float(fp))

    def _grow_locked(self):
        if len(self._shards) >= self.max_shards:
            raise OverflowError("max_shards=%d reached, refusing to grow" % self.max_shards)
        last = self._shards[-1]
        shard = self._new_shard(last.capacity * self.growth, last.fp * self.ratio)
        self._shards.append(shard)
        return shard

    def add(self, item):
        with self._lock:
            shard = self._shards[-1]
            if len(shard.bf) >= shard.capacity:
                shard = self._grow_locked()
            shard.bf.add(item)

    def __contains__(self, item):
        for shard in self._shards:
            if item in shard.bf:
                return True
        return False

    def __len__(self):
        return sum(len(shard.bf) for shard in self._shards)

    @property
    def shard_count(self):
        return len(self._shards)

    @property
    def overall_fp_rate(self):
        """整体假阳性率：1 - ∏(1 - p_i)，p_i 按各片实际写入量估算。"""
        miss = 1.0
        for shard in self._shards:
            n = len(shard.bf)
            if n:
                k, m = shard.bf.num_hashes, shard.bf.num_bits
                miss *= 1.0 - (1.0 - math.exp(-k * n / m)) ** k
        return 1.0 - miss

    def to_bytes(self):
        out = [_HEADER.pack(MAGIC, self.initial_capacity, self.fp_rate,
                            self.growth, self.ratio, self.max_shards)]
        for shard in self._shards:
            blob = shard.bf.to_bytes()
            out.append(_SHARD_META.pack(shard.capacity, shard.fp, len(blob)))
            out.append(blob)
        return b"".join(out)

    @classmethod
    def from_bytes(cls, blob):
        if blob[:4] == LEGACY_MAGIC:
            return cls._from_legacy(blob)
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, initial_capacity, fp_rate, growth, ratio, max_shards = _HEADER.unpack(
            blob[: _HEADER.size])
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        obj = cls(initial_capacity, fp_rate, growth, ratio, max_shards)
        obj._shards = []
        off = _HEADER.size
        while off < len(blob):
            if len(blob) - off < _SHARD_META.size:
                raise ValueError("truncated shard metadata")
            capacity, fp, blob_len = _SHARD_META.unpack(blob[off: off + _SHARD_META.size])
            off += _SHARD_META.size
            if len(blob) - off < blob_len:
                raise ValueError("truncated shard payload")
            bf = BloomFilter.from_bytes(blob[off: off + blob_len])
            obj._shards.append(_Shard(bf, capacity, fp))
            off += blob_len
        if not obj._shards:
            raise ValueError("no shards in blob")
        return obj

    @classmethod
    def _from_legacy(cls, blob):
        """老版本 BLM1 单实例文件：按单片加载，容量由位数组尺寸反推。"""
        bf = BloomFilter.from_bytes(blob)
        capacity = max(1, int(round(bf.num_bits * math.log(2) / bf.num_hashes)))
        fp = (1.0 - math.exp(-bf.num_hashes * capacity / bf.num_bits)) ** bf.num_hashes
        fp = min(max(fp, 1e-12), 0.5)
        obj = cls(initial_capacity=capacity)
        obj._shards = [_Shard(bf, capacity, fp)]
        return obj
