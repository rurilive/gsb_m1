"""分桶基数估算。

BucketSketch 用 HyperLogLog 思路估不同 key 的个数：每个 key 哈希后按
高位落到某个桶，桶里记低位前导零的最大值。内存只占 2**bits 个字节，
灌多少 key 都不涨；count() 的相对误差约 1.04 / sqrt(桶数)，默认
bits=12（4096 字节）时约 1.6%。小基数走线性计数修正，桶还空着大
半时不会给出离谱的数。merge 按桶取 max，满足交换律、结合律、幂等，
与先合数据再从零建完全一致。
"""

import hashlib
import math
import threading

_HASH_BITS = 64


def _key_bytes(key):
    """把 key 变成稳定的字节串，保证同一 key 永远落同一个桶。"""
    return repr(key).encode("utf-8")


class BucketSketch:
    """固定内存的分桶基数估算器。bits 是桶数的对数，seed 决定哈希。"""

    def __init__(self, bits=12, seed=0):
        if isinstance(bits, bool) or not isinstance(bits, int):
            raise TypeError(f"bits 必须是 int，收到 {type(bits).__name__}")
        if not 4 <= bits <= 16:
            raise ValueError(f"bits 必须在 4..16 之间，收到 {bits}")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise TypeError(f"seed 必须是 int，收到 {type(seed).__name__}")
        if not 0 <= seed < 1 << _HASH_BITS:
            raise ValueError(f"seed 必须在 0..2**64-1 之间，收到 {seed}")
        self.bits = bits
        self.seed = seed
        self.size = 1 << bits
        self._registers = bytearray(self.size)
        self._key = seed.to_bytes(8, "little")
        self._lock = threading.Lock()

    def _hash(self, key):
        digest = hashlib.blake2b(_key_bytes(key), digest_size=8, key=self._key)
        return int.from_bytes(digest.digest(), "little")

    def add(self, key):
        """记一个 key；返回值是桶值是否被推高（近似“像是新 key”）。"""
        hashed = self._hash(key)
        index = hashed >> (_HASH_BITS - self.bits)
        rest = hashed & ((1 << (_HASH_BITS - self.bits)) - 1)
        width = _HASH_BITS - self.bits
        rank = width - rest.bit_length() + 1 if rest else width + 1
        with self._lock:
            if rank <= self._registers[index]:
                return False
            self._registers[index] = rank
            return True

    def count(self):
        """不同 key 数的估算值。"""
        with self._lock:
            registers = bytes(self._registers)
        zeros = registers.count(0)
        if zeros == self.size:
            return 0
        indicator = sum(2.0 ** -value for value in registers)
        alpha = 0.7213 / (1 + 1.079 / self.size)
        raw = alpha * self.size * self.size / indicator
        if raw <= 2.5 * self.size and zeros:
            return int(round(self.size * math.log(self.size / zeros)))
        return int(round(raw))

    def merge(self, other):
        """与另一个估算器合并，返回新估算器；两边都不动。"""
        if not isinstance(other, BucketSketch):
            raise TypeError(f"只能合并 BucketSketch，收到 {type(other).__name__}")
        if self.bits != other.bits or self.seed != other.seed:
            raise ValueError("bits 或 seed 不一致的估算器不能合并")
        with self._lock:
            left = bytes(self._registers)
        with other._lock:
            right = bytes(other._registers)
        merged = BucketSketch(self.bits, self.seed)
        merged._registers = bytearray(map(max, left, right))
        return merged

    def registers(self):
        """桶值的只读快照（bytes），供落盘与对拍使用。"""
        with self._lock:
            return bytes(self._registers)

    @classmethod
    def from_registers(cls, bits, seed, registers):
        """从桶值快照重建估算器；长度不对抛 ValueError。"""
        sketch = cls(bits, seed)
        data = bytes(registers)
        if len(data) != sketch.size:
            raise ValueError(f"桶值长度必须是 {sketch.size}，收到 {len(data)}")
        max_rank = _HASH_BITS - bits + 1
        if any(value > max_rank for value in data):
            raise ValueError(f"桶值不能超过 {max_rank}")
        sketch._registers = bytearray(data)
        return sketch
