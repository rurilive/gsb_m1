"""可在线扩容的分片布隆过滤器。

数据涨满当前片就追加一片新的，旧片冻结不动；查询遍历所有片取并集。
磁盘格式为 BLM2，同时兼容老版本 BLM1 单实例文件的读回。
"""
import math
import os
import struct
import tempfile
import threading
import warnings

from .filter import MAGIC as _MAGIC_V1
from .filter import BloomFilter, _HEADER as _V1_HEADER

SHARD_MAGIC = b"BLM2"
# shard_capacity, max_shards, count, fp_rate, num_shards
_HEADER_V2 = struct.Struct(">IIQdI")
_SHARD_LIMIT = struct.Struct(">Q")
_V1_HEADER_SIZE = _V1_HEADER.size


def _popcount(buf):
    """统计字节串里置位的 bit 数。"""
    return bin(int.from_bytes(bytes(buf), "big")).count("1")


class ShardedBloomFilter:
    """多分片布隆过滤器，支持在线添片、整体假阳性率与新旧两种磁盘格式。"""

    def __init__(self, shard_capacity, fp_rate=0.01, max_shards=16, auto_grow=True):
        if shard_capacity <= 0:
            raise ValueError("shard_capacity must be positive")
        if not 0.0 < fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        if max_shards < 0:
            raise ValueError("max_shards must be >= 0 (0 means unlimited)")
        self.shard_capacity = int(shard_capacity)
        self.fp_rate = float(fp_rate)
        self.max_shards = int(max_shards)
        self.auto_grow = bool(auto_grow)
        first = BloomFilter(self.shard_capacity, self.fp_rate)
        self._shards = [first]
        self._limits = [self.shard_capacity]
        self._lock = threading.RLock()
        self._capped = False

    # ---- 基础状态 -----------------------------------------------------

    @property
    def shards(self):
        with self._lock:
            return tuple(self._shards)

    @property
    def num_shards(self):
        with self._lock:
            return len(self._shards)

    @property
    def capped(self):
        """是否已撞到片数上限（内存兜底已触发）。"""
        return self._capped

    def __len__(self):
        with self._lock:
            return sum(len(shard) for shard in self._shards)

    def _can_grow(self):
        return self.max_shards <= 0 or len(self._shards) < self.max_shards

    def _append_shard(self, capacity, fp_rate):
        shard = BloomFilter(capacity, fp_rate)
        self._shards.append(shard)
        self._limits.append(int(capacity))
        return shard

    # ---- 在线添片 -----------------------------------------------------

    def add_shard(self, capacity=None, fp_rate=None):
        """在线追加一片新的；旧片原封不动。返回新片下标，到顶抛 RuntimeError。"""
        cap = self.shard_capacity if capacity is None else int(capacity)
        p = self.fp_rate if fp_rate is None else float(fp_rate)
        if cap <= 0:
            raise ValueError("capacity must be positive")
        if not 0.0 < p < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        with self._lock:
            if not self._can_grow():
                raise RuntimeError("max shard count reached: %d" % self.max_shards)
            self._append_shard(cap, p)
            return len(self._shards) - 1

    # ---- 写入与查询 ---------------------------------------------------

    def add(self, item):
        with self._lock:
            active = self._shards[-1]
            limit = self._limits[-1]
            if len(active) >= limit:
                if self.auto_grow and self._can_grow():
                    active = self._append_shard(self.shard_capacity, self.fp_rate)
                elif not self._capped:
                    self._capped = True
                    warnings.warn(
                        "shard cap reached; writes continue into the active shard",
                        RuntimeWarning,
                        stacklevel=2,
                    )
            active.add(item)

    def __contains__(self, item):
        # 同一条数据可能落在任意一片：任一片命中即为存在，每片都要查。
        with self._lock:
            shards = tuple(self._shards)
        for shard in shards:
            if item in shard:
                return True
        return False

    # ---- 整体假阳性率 -------------------------------------------------

    @property
    def fp_rate_overall(self):
        """各片实际置位比例合成的整体假阳性率。

        单片对未写入项误报的概率为 (置位数/位数)^哈希数；
        多片取并集后：1 - ∏(1 - 单片误报率)。
        """
        with self._lock:
            shards = tuple(self._shards)
        survive = 1.0
        for shard in shards:
            filled = _popcount(shard._bits) / shard.num_bits
            survive *= 1.0 - filled ** shard.num_hashes
        return 1.0 - survive

    # ---- 序列化 -------------------------------------------------------

    def to_bytes(self):
        with self._lock:
            count = sum(len(shard) for shard in self._shards)
            header = SHARD_MAGIC + _HEADER_V2.pack(
                self.shard_capacity,
                self.max_shards,
                count,
                self.fp_rate,
                len(self._shards),
            )
            parts = [header]
            for limit, shard in zip(self._limits, self._shards):
                parts.append(_SHARD_LIMIT.pack(limit))
                parts.append(shard.to_bytes())
            return b"".join(parts)

    @classmethod
    def from_bytes(cls, blob, shard_capacity=None, fp_rate=None, max_shards=None):
        if len(blob) < 4:
            raise ValueError("blob too short")
        magic = blob[:4]
        if magic == _MAGIC_V1:
            return cls._from_v1(blob, shard_capacity, fp_rate, max_shards)
        if magic != SHARD_MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        if len(blob) < 4 + _HEADER_V2.size:
            raise ValueError("blob too short")
        cap, top, count, p, num_shards = _HEADER_V2.unpack(
            blob[4 : 4 + _HEADER_V2.size]
        )
        obj = cls.__new__(cls)
        obj.shard_capacity = cap
        obj.fp_rate = p
        obj.max_shards = top
        obj.auto_grow = True
        obj._shards = []
        obj._limits = []
        obj._lock = threading.RLock()
        offset = 4 + _HEADER_V2.size
        for _ in range(num_shards):
            if offset + _SHARD_LIMIT.size > len(blob):
                raise ValueError("truncated shard entry")
            (limit,) = _SHARD_LIMIT.unpack(blob[offset : offset + _SHARD_LIMIT.size])
            offset += _SHARD_LIMIT.size
            _, _, _, payload_len = cls._read_v1_header(blob, offset)
            end = offset + _V1_HEADER_SIZE + payload_len
            if end > len(blob):
                raise ValueError("truncated shard payload")
            shard = BloomFilter.from_bytes(blob[offset:end])
            obj._shards.append(shard)
            obj._limits.append(limit)
            offset = end
        if offset != len(blob):
            raise ValueError("trailing bytes after shards")
        if sum(len(s) for s in obj._shards) != count:
            raise ValueError("shard count mismatch")
        if num_shards == 0:
            raise ValueError("no shards in blob")
        active = obj._shards[-1]
        obj._capped = (
            top > 0
            and num_shards >= top
            and len(active) >= obj._limits[-1]
        )
        return obj

    @staticmethod
    def _read_v1_header(blob, offset):
        magic, num_bits, num_hashes, shard_count = _V1_HEADER.unpack(
            blob[offset : offset + _V1_HEADER.size]
        )
        if magic != _MAGIC_V1:
            raise ValueError("bad shard magic: %r" % (magic,))
        return num_bits, num_hashes, shard_count, (num_bits + 7) // 8

    @classmethod
    def _from_v1(cls, blob, shard_capacity, fp_rate, max_shards):
        legacy = BloomFilter.from_bytes(blob)
        # 由老片几何尺寸反推它当初按多少容量配的，作为它自己的写满阈值。
        derived_cap = max(
            1, int(round(legacy.num_bits * math.log(2) / legacy.num_hashes))
        )
        derived_p = math.exp(-(legacy.num_bits * math.log(2) ** 2) / derived_cap)
        derived_p = min(max(derived_p, 1e-9), 1.0 - 1e-9)
        obj = cls.__new__(cls)
        obj.shard_capacity = (
            int(shard_capacity) if shard_capacity is not None else derived_cap
        )
        obj.fp_rate = float(fp_rate) if fp_rate is not None else derived_p
        obj.max_shards = 16 if max_shards is None else int(max_shards)
        obj.auto_grow = True
        obj._shards = [legacy]
        obj._limits = [derived_cap]
        obj._lock = threading.RLock()
        obj._capped = False
        return obj

    # ---- 磁盘持久化（原子落盘） ---------------------------------------

    def save(self, path):
        data = self.to_bytes()
        directory = os.path.dirname(os.path.abspath(path))
        fd, tmp_path = tempfile.mkstemp(prefix=".bloomx-", dir=directory)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path, **kwargs):
        with open(path, "rb") as handle:
            blob = handle.read()
        return cls.from_bytes(blob, **kwargs)
