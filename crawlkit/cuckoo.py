"""可删除的布谷鸟过滤器：指纹加双候选桶，踢出链超限就翻倍扩容重排，全程迭代。

每个键存一份 fp_bits 位指纹（连同定位用的 h1 拼成一个槽位整数），落在两个
候选桶之一；两桶都满就随机踢出既有指纹让座，被踢的指纹换到它的另一个候选桶，
链式让座位超过 _MAX_KICKS 就扩容重排。桶里只挪不丢，所以已加未删的键任何
时刻都命中；说在仍可能没加过（指纹撞车），这是近似结构的底色。
"""

import math
import random
import struct

from .hashing import fingerprint, hash_pair

MAGIC = b"DCFK"
# magic, fp_bits, bucket_size, num_buckets, capacity, added
_HEADER = struct.Struct(">4sBBQQQ")

_BUCKET_SIZE = 2
_MAX_KICKS = 500
_LOAD_FACTOR = 0.8
_MIX_CONSTANT = 0x9E3779B97F4A7C15
_MASK64 = (1 << 64) - 1


def fp_bits_for_rate(fp_rate, bucket_size=_BUCKET_SIZE):
    """按目标误判率估指纹位数：fp 约等于 2 * bucket_size / 2**fp_bits。"""
    if not 0.0 < fp_rate < 1.0:
        raise ValueError("fp_rate must be in (0, 1)")
    return max(1, int(math.ceil(math.log2(2.0 * bucket_size / fp_rate))))


class CuckooFilter:
    """支持删除的近似集合，接口与 BloomFilter 对齐，外加 remove。

    capacity 只用来定初始桶数，装载堆高会自行翻倍扩容；fp_bits 定指纹
    位数，位数越高误判越低。查询说不在就一定不在，说在可能没加过。
    """

    def __init__(self, capacity, fp_bits=12):
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        fp_bits = int(fp_bits)
        if not 1 <= fp_bits <= 32:
            raise ValueError("fp_bits must be in [1, 32]")
        self.capacity = capacity
        self.fp_bits = fp_bits
        self.bucket_size = _BUCKET_SIZE
        self.num_buckets = max(
            8, int(math.ceil(capacity / (self.bucket_size * _LOAD_FACTOR)))
        )
        self._buckets = [[] for _ in range(self.num_buckets)]
        self._fp_mask = (1 << fp_bits) - 1
        self._added = 0
        self._rng = random.Random(0xC0FFEE)

    def _slot_bytes(self):
        return (64 + self.fp_bits + 7) // 8

    @staticmethod
    def _delta(fp, num_buckets):
        mix = (fp * _MIX_CONSTANT) & _MASK64
        return 1 + mix % (num_buckets - 1)

    def _candidates(self, h1, fp, num_buckets):
        i1 = h1 % num_buckets
        return i1, (i1 + self._delta(fp, num_buckets)) % num_buckets

    def _find_fp(self, h1, fp):
        i1, i2 = self._candidates(h1, fp, self.num_buckets)
        mask = self._fp_mask
        for slot in self._buckets[i1]:
            if slot & mask == fp:
                return True
        for slot in self._buckets[i2]:
            if slot & mask == fp:
                return True
        return False

    def _find_slot(self, slot, h1, fp):
        """精确找 (h1, fp) 都相同的槽位：加键幂等和删除都按完整身份认，
        同指纹但 h1 不同的别的键不算数，谁也拖累不了谁。"""
        i1, i2 = self._candidates(h1, fp, self.num_buckets)
        return slot in self._buckets[i1] or slot in self._buckets[i2]

    def _place(self, slot, buckets, num_buckets):
        """把槽位放进给定表，成功返回 None；踢出链超限返回手里没放下的槽位。

        全程迭代；表里的槽位只挪不丢，没放下的那个由返回值交还给调用方。
        """
        mask = self._fp_mask
        fp = slot & mask
        i1, i2 = self._candidates(slot >> self.fp_bits, fp, num_buckets)
        b1 = buckets[i1]
        b2 = buckets[i2]
        if len(b1) < self.bucket_size:
            b1.append(slot)
            return None
        if len(b2) < self.bucket_size:
            b2.append(slot)
            return None
        rng = self._rng
        i = i1 if rng.random() < 0.5 else i2
        cur = slot
        for _ in range(_MAX_KICKS):
            bucket = buckets[i]
            j = rng.randrange(len(bucket))
            cur, bucket[j] = bucket[j], cur
            cur_fp = cur & mask
            c1, c2 = self._candidates(cur >> self.fp_bits, cur_fp, num_buckets)
            i = c2 if i == c1 else c1
            nxt = buckets[i]
            if len(nxt) < self.bucket_size:
                nxt.append(cur)
                return None
        return cur

    def _grow(self, extra):
        """桶数翻倍，全部既有槽位（含 extra）重排进新表，旧表原地不动直到成功。"""
        slots = [s for bucket in self._buckets for s in bucket]
        slots.append(extra)
        n = self.num_buckets
        while True:
            n *= 2
            fresh = [[] for _ in range(n)]
            ok = True
            for s in slots:
                if self._place(s, fresh, n) is not None:
                    ok = False
                    break
            if ok:
                self.num_buckets = n
                self._buckets = fresh
                return

    def add(self, key):
        """加入一个键。同一个键重复加是幂等的，只占一个槽。"""
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        slot = (h1 << self.fp_bits) | fp
        if self._find_slot(slot, h1, fp):
            return
        pending = self._place(slot, self._buckets, self.num_buckets)
        if pending is not None:
            self._grow(pending)
        self._added += 1

    def remove(self, key):
        """撤掉一个键，撤掉了就查不到。没加过返回 False，别的键不受影响。"""
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        slot = (h1 << self.fp_bits) | fp
        i1, i2 = self._candidates(h1, fp, self.num_buckets)
        for i in (i1, i2):
            bucket = self._buckets[i]
            for pos, stored in enumerate(bucket):
                if stored == slot:
                    del bucket[pos]
                    self._added -= 1
                    return True
        return False

    def __contains__(self, key):
        h1, h2 = hash_pair(key)
        return self._find_fp(h1, fingerprint(h2, self.fp_bits))

    def __len__(self):
        return self._added

    def stats(self):
        """计数快照，独立 dict。"""
        return {
            "added": self._added,
            "capacity": self.capacity,
            "fp_bits": self.fp_bits,
            "num_buckets": self.num_buckets,
            "bucket_size": self.bucket_size,
            "size_bytes": self.num_buckets * self.bucket_size * self._slot_bytes(),
        }

    def to_bytes(self):
        """落盘格式：定长头加定宽槽位流，空槽补零（真指纹恒非零）。"""
        head = _HEADER.pack(
            MAGIC,
            self.fp_bits,
            self.bucket_size,
            self.num_buckets,
            self.capacity,
            self._added,
        )
        width = self._slot_bytes()
        out = bytearray(head)
        pad = b"\x00" * width
        for bucket in self._buckets:
            for slot in bucket:
                out += slot.to_bytes(width, "big")
            for _ in range(self.bucket_size - len(bucket)):
                out += pad
        return bytes(out)

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, fp_bits, bucket_size, num_buckets, capacity, added = _HEADER.unpack(
            blob[:_HEADER.size]
        )
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        if not 1 <= fp_bits <= 32:
            raise ValueError("bad fp_bits: %r" % (fp_bits,))
        if bucket_size < 1:
            raise ValueError("bad bucket_size: %r" % (bucket_size,))
        if num_buckets < 2:
            raise ValueError("bad num_buckets: %r" % (num_buckets,))
        width = (64 + fp_bits + 7) // 8
        payload = blob[_HEADER.size:]
        if len(payload) != num_buckets * bucket_size * width:
            raise ValueError("slot payload length mismatch")
        obj = cls.__new__(cls)
        obj.capacity = capacity
        obj.fp_bits = fp_bits
        obj.bucket_size = bucket_size
        obj.num_buckets = num_buckets
        obj._fp_mask = (1 << fp_bits) - 1
        obj._rng = random.Random(0xC0FFEE)
        obj._buckets = []
        count = 0
        off = 0
        for _ in range(num_buckets):
            bucket = []
            for _ in range(bucket_size):
                slot = int.from_bytes(payload[off:off + width], "big")
                off += width
                if slot:
                    if not slot & obj._fp_mask:
                        raise ValueError("zero fingerprint in slot")
                    bucket.append(slot)
                    count += 1
            obj._buckets.append(bucket)
        if count != added:
            raise ValueError("added count mismatch")
        obj._added = count
        return obj
