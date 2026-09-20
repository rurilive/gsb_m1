"""可在线扩容的分片布隆过滤器。

容量不够时调用 add_shard() 追加一片全新的 BloomFilter，旧片原封不动；
写入永远落在最新一片，查询遍历所有片。进程重启可用 from_bytes() 读回，
老版本 BLM1 单实例格式也能自动识别。片数有上限，防止内存被无限吃满。
"""
import math
import struct
import threading

from .filter import BloomFilter, MAGIC as _MAGIC_V1

MAGIC = b"BLM2"
_HEADER = struct.Struct(">4sIIQ")  # magic, max_shards, target_fp_rate(定点), reserved
DEFAULT_MAX_SHARDS = 16
# 目标假阳性率在磁盘上按 64 位定点小数保存
_FP_SCALE = 2 ** 32


class ShardCapacityError(RuntimeError):
    """片数已达上限，内存兜底拒绝继续添片。"""


class ShardBloomFilter:
    """由若干定容 BloomFilter 串起来的可增长布隆过滤器。"""

    def __init__(self, capacity, fp_rate=0.01, max_shards=DEFAULT_MAX_SHARDS):
        first = BloomFilter(capacity, fp_rate)
        self._shards = [first]
        self._shard_capacity = first.capacity
        self.target_fp_rate = first.fp_rate
        self.max_shards = max_shards
        self._lock = threading.Lock()

    # ---- 基本属性 -------------------------------------------------------

    @property
    def shards(self):
        with self._lock:
            return list(self._shards)

    @property
    def shard_capacity(self):
        return self._shard_capacity

    # ---- 写入与查询 -----------------------------------------------------

    def add(self, item):
        # 置位与计数整体持锁：bytearray 的 |= 在字节码层面可能交错，
        # 多线程裸写会丢位从而产生假阴性。add_shard 也持同一把锁，
        # 添片期间的写入要么完整进旧片（旧片仍在列表里被查询），
        # 要么等新片挂上后完整进新片，一条都不会丢。
        with self._lock:
            self._shards[-1].add(item)

    def add_shard(self, capacity=None, fp_rate=None):
        """在线追加一片。旧片冻结不动，之后的写入全部进新片。"""
        with self._lock:
            if len(self._shards) >= self.max_shards:
                raise ShardCapacityError(
                    "shard limit %d reached; refusing to grow further" % self.max_shards
                )
            shard = BloomFilter(
                capacity if capacity is not None else self._shard_capacity,
                fp_rate if fp_rate is not None else self.target_fp_rate,
            )
            self._shards.append(shard)
            return len(self._shards) - 1

    def __contains__(self, item):
        # 快照后逐片查；漏掉任意一片都可能产生假阴性，所以必须全查。
        for shard in self.shards:
            if item in shard:
                return True
        return False

    def __len__(self):
        with self._lock:
            return sum(len(shard) for shard in self._shards)

    # ---- 假阳性率 -------------------------------------------------------

    @staticmethod
    def _shard_fp_rate(shard):
        """单片在当前写入量下的实际假阳性率。

        n 次写入后每位仍为 0 的概率是 e^{-kn/m}，故假阳性率
        (1 - e^{-kn/m})^k；写入量超过容量时照样成立。
        """
        if shard.num_hashes <= 0 or shard._count == 0:
            return 0.0
        fill = 1.0 - math.exp(
            -shard.num_hashes * shard._count / shard.num_bits
        )
        return fill ** shard.num_hashes

    def fp_rate(self):
        """整体假阳性率：1 - 各片“判不命中”概率之积，只有一个数。"""
        with self._lock:
            shards = list(self._shards)
        miss = 1.0
        for shard in shards:
            miss *= 1.0 - self._shard_fp_rate(shard)
        return 1.0 - miss

    # ---- 磁盘持久化 -----------------------------------------------------

    def save(self, path):
        with open(path, "wb") as fh:
            fh.write(self.to_bytes())

    @classmethod
    def load(cls, path):
        with open(path, "rb") as fh:
            return cls.from_bytes(fh.read())

    def to_bytes(self):
        with self._lock:
            header = _HEADER.pack(
                MAGIC,
                self.max_shards,
                int(round(self.target_fp_rate * _FP_SCALE)),
                0,
            )
            parts = [header, struct.pack(">I", len(self._shards))]
            for shard in self._shards:
                parts.append(struct.pack(">Q", shard.capacity))
                payload = shard.to_bytes()
                parts.append(struct.pack(">Q", len(payload)))
                parts.append(payload)
            return b"".join(parts)

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < 4:
            raise ValueError("blob too short")
        if blob[:4] == _MAGIC_V1:
            return cls._from_v1(blob)
        if blob[:4] != MAGIC:
            raise ValueError("bad magic: %r" % (blob[:4],))
        if len(blob) < _HEADER.size + 4:
            raise ValueError("blob too short")
        magic, max_shards, fp_fixed, _reserved = _HEADER.unpack(blob[: _HEADER.size])
        del magic
        offset = _HEADER.size
        (num_shards,) = struct.unpack_from(">I", blob, offset)
        offset += 4
        shards = []
        for _ in range(num_shards):
            (capacity, size) = struct.unpack_from(">QQ", blob, offset)
            offset += 16
            payload = blob[offset : offset + size]
            if len(payload) != size:
                raise ValueError("truncated shard payload")
            shard = BloomFilter.from_bytes(payload)
            # BLM1 子格式本身不存容量，由外层框架补回，保证假阳性率算得准
            shard.capacity = capacity
            shard.fp_rate = 0.5 ** shard.num_hashes
            shards.append(shard)
            offset += size
        if not shards:
            raise ValueError("no shards in blob")
        obj = cls.__new__(cls)
        obj._shards = shards
        obj.max_shards = max_shards
        obj.target_fp_rate = fp_fixed / _FP_SCALE
        obj._lock = threading.Lock()
        obj._shard_capacity = shards[0].capacity
        return obj

    @classmethod
    def _from_v1(cls, blob):
        """把老版本 BLM1 单实例文件整体包成唯一一片，历史数据原样保留。"""
        shard = BloomFilter.from_bytes(blob)
        obj = cls.__new__(cls)
        obj._shards = [shard]
        obj.max_shards = DEFAULT_MAX_SHARDS
        obj._lock = threading.Lock()
        if shard.capacity > 0:
            obj._shard_capacity = shard.capacity
            obj.target_fp_rate = shard.fp_rate
        else:
            # 老格式不存容量/目标率，只能从位数和哈希数反推
            obj._shard_capacity = cls._guess_capacity(shard)
            obj.target_fp_rate = 0.5 ** shard.num_hashes
            shard.capacity = obj._shard_capacity
            shard.fp_rate = obj.target_fp_rate
        return obj

    @staticmethod
    def _guess_capacity(shard):
        k = max(1, shard.num_hashes)
        return max(1, int(round(shard.num_bits * math.log(2) / k)))
