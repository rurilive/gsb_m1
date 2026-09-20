"""可在线扩容的分片布隆过滤器。

每片仍是一个固定容量的 BloomFilter，旧片冻结只查不写，
写满后挂一片更大容量的新片；查询必须问遍所有片，漏一片就有假阴性。
"""
import math
import os
import struct
import threading

from .filter import MAGIC as _SHARD_MAGIC, BloomFilter

MAGIC = b"BLMS"
_HEADER = struct.Struct(">4sIQdd")  # magic, max_shards, capacity, fp_rate, tightening
_ENTRY = struct.Struct(">QdI")       # capacity, target_fp, blob_len


class ShardFullError(RuntimeError):
    """片数已达上限，兜底策略下无法再挂新片。"""


class ShardedBloomFilter:
    """多片布隆过滤器。

    capacity / fp_rate 描述单片容量与整体假阳性率上限，max_shards
    是机器内存兜底；tightening 控制逐片目标假阳性率的几何收紧比例，
    保证所有片的目标假阳性率之和不超过 fp_rate。
    """

    def __init__(self, capacity, fp_rate=0.01, max_shards=32, tightening=0.5):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0.0 < fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        if max_shards < 1:
            raise ValueError("max_shards must be >= 1")
        if not 0.0 < tightening < 1.0:
            raise ValueError("tightening must be in (0, 1)")
        self.capacity = int(capacity)
        self.target_fp_rate = float(fp_rate)
        self.max_shards = int(max_shards)
        self.tightening = float(tightening)
        self._shards = []          # [(BloomFilter, capacity, target_fp)]
        self._sealed = False       # 已到 max_shards，只能往末片兜底写
        self._lock = threading.RLock()
        self._append_shard()

    # ---- 片管理 -----------------------------------------------------

    def _next_target_fp(self):
        if not self._shards:
            return self.target_fp_rate * (1.0 - self.tightening)
        return self._shards[-1][2] * self.tightening

    def _append_shard(self, target_fp=None):
        """调用方需持有锁。返回新片下标。"""
        if len(self._shards) >= self.max_shards:
            raise ShardFullError(
                "shard limit %d reached" % self.max_shards)
        if target_fp is None:
            target_fp = self._next_target_fp()
        bf = BloomFilter(self.capacity, target_fp)
        self._shards.append((bf, self.capacity, float(target_fp)))
        return len(self._shards) - 1

    def add_shard(self, fp_rate=None):
        """显式在线挂一片新片，旧片原封不动；返回新片下标。"""
        with self._lock:
            if len(self._shards) >= self.max_shards:
                raise ShardFullError(
                    "shard limit %d reached" % self.max_shards)
            return self._append_shard(fp_rate)

    def _ensure_head_writable(self):
        """调用方需持有锁。写满则自动添片，封顶后兜底写末片。"""
        bf, cap, _target = self._shards[-1]
        if len(bf) < cap or self._sealed:
            return
        try:
            self._append_shard()
        except ShardFullError:
            self._sealed = True

    @property
    def num_shards(self):
        with self._lock:
            return len(self._shards)

    @property
    def sealed(self):
        """内存兜底已生效：不再添片，新写全部落入末片。"""
        with self._lock:
            return self._sealed

    # ---- 写 / 查 / 计数 ---------------------------------------------

    def add(self, item):
        with self._lock:
            self._ensure_head_writable()
            self._shards[-1][0].add(item)

    def __contains__(self, item):
        with self._lock:
            shards = list(self._shards)
        # 同一条数据可能落在任意一片：所有片都说否，才是否。
        for bf, _cap, _target in shards:
            if item in bf:
                return True
        return False

    def __len__(self):
        with self._lock:
            return sum(len(bf) for bf, _c, _t in self._shards)

    # ---- 整体假阳性率 -----------------------------------------------

    @staticmethod
    def _shard_fp(bf):
        """单片按真实写入量算的假阳性率 (1-e^{-kn/m})^k。"""
        n = len(bf)
        if n <= 0:
            return 0.0
        m = bf.num_bits
        k = bf.num_hashes
        return (1.0 - math.exp(-k * n / m)) ** k

    @property
    def fp_rate(self):
        """整体假阳性率：任一单片误判即误判，1 - Π(1 - p_i)。"""
        with self._lock:
            shards = list(self._shards)
        miss = 1.0
        for bf, _cap, _target in shards:
            miss *= 1.0 - self._shard_fp(bf)
        return 1.0 - miss

    # ---- 序列化 -----------------------------------------------------

    def to_bytes(self):
        with self._lock:
            out = [_HEADER.pack(
                MAGIC, self.max_shards, self.capacity,
                self.target_fp_rate, self.tightening)]
            out.append(struct.pack(">I", len(self._shards)))
            for bf, cap, target in self._shards:
                blob = bf.to_bytes()
                out.append(_ENTRY.pack(cap, target, len(blob)))
                out.append(blob)
        return b"".join(out)

    @classmethod
    def from_bytes(cls, blob, capacity=None, fp_rate=None,
                   max_shards=None, tightening=0.5):
        """从磁盘读回状态；老版本 BLM1 单实例格式也认。"""
        if len(blob) < 4:
            raise ValueError("blob too short")
        magic = blob[:4]
        if magic == _SHARD_MAGIC:
            return cls._from_legacy(
                blob, capacity, fp_rate, max_shards, tightening)
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        _magic, h_max, h_cap, h_fp, h_tight = _HEADER.unpack(blob[:_HEADER.size])
        off = _HEADER.size
        (count,) = struct.unpack(">I", blob[off:off + 4])
        off += 4
        obj = cls.__new__(cls)
        obj.capacity = h_cap
        obj.target_fp_rate = h_fp
        obj.max_shards = h_max
        obj.tightening = h_tight
        obj._shards = []
        obj._sealed = False
        obj._lock = threading.RLock()
        for _i in range(count):
            cap, target, blob_len = _ENTRY.unpack(blob[off:off + _ENTRY.size])
            off += _ENTRY.size
            piece = blob[off:off + blob_len]
            off += blob_len
            if len(piece) != blob_len:
                raise ValueError("truncated shard payload")
            obj._shards.append((BloomFilter.from_bytes(piece), cap, target))
        if off != len(blob):
            raise ValueError("trailing bytes after shards")
        if not obj._shards:
            raise ValueError("sharded filter has no shards")
        obj._sealed = len(obj._shards) >= obj.max_shards
        return obj

    @classmethod
    def _from_legacy(cls, blob, capacity, fp_rate, max_shards, tightening):
        old = BloomFilter.from_bytes(blob)
        if not 0.0 < tightening < 1.0:
            raise ValueError("tightening must be in (0, 1)")
        # 老格式里没有容量与目标假阳性率，只能从位数/哈希数反推。
        inferred_cap = max(1, int(round(
            old.num_bits * math.log(2) / old.num_hashes)))
        cap = int(capacity) if capacity is not None else inferred_cap
        if cap <= 0:
            raise ValueError("capacity must be positive")
        if fp_rate is None:
            fp_rate = (0.5 ** old.num_hashes) / (1.0 - tightening)
        if not 0.0 < fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        limit = int(max_shards) if max_shards is not None else 32
        if limit < 1:
            raise ValueError("max_shards must be >= 1")
        obj = cls.__new__(cls)
        obj.capacity = cap
        obj.target_fp_rate = float(fp_rate)
        obj.max_shards = limit
        obj.tightening = float(tightening)
        obj._shards = [(old, cap, float(fp_rate) * (1.0 - tightening))]
        obj._sealed = False
        obj._lock = threading.RLock()
        return obj

    def save(self, path):
        """原子落盘：临时文件写完再 rename，崩溃也不会留半截状态。"""
        data = self.to_bytes()
        directory = os.path.dirname(os.path.abspath(path))
        tmp = "%s.tmp.%d" % (path, os.getpid())
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        try:
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass

    @classmethod
    def load(cls, path, **overrides):
        with open(path, "rb") as fh:
            return cls.from_bytes(fh.read(), **overrides)
