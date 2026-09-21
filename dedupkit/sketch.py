"""分桶基数估算（HyperLogLog 风格）。

BucketSketch 用固定数量的桶（2**bits 个，每桶一字节）记录散列值的
前导零数，用调和平均数估算不同 key 的个数，内存与灌入的 key 数无关。
基数还小、空桶不少时改用线性计数修正，避免数据比桶还少却冒出离奇值。

桶位按位取 max 正好等价于把两边数据合在一起重建，所以 merge 满足
交换律、结合律、幂等（任意顺序、合几遍都一样）。
"""

import hashlib
import json
import math
import threading

DEFAULT_BITS = 12
MIN_BITS = 4
MAX_BITS = 18


def _stable_payload(seed):
    """带域分隔的 blake2b key，把不同 seed 混成不相干的散列空间。"""
    material = b"dedupkit.BucketSketch\x00" + int(seed & ((1 << 128) - 1)).to_bytes(
        16, "little"
    )
    return material


class BucketSketch:
    """定容分桶基数估算器；bits 定桶数，seed 换一套散列。"""

    def __init__(self, bits=DEFAULT_BITS, seed=0):
        if not isinstance(bits, int) or isinstance(bits, bool):
            raise TypeError(f"bits 必须是 int，收到 {type(bits).__name__}")
        if not MIN_BITS <= bits <= MAX_BITS:
            raise ValueError(f"bits 必须在 [{MIN_BITS}, {MAX_BITS}] 内，收到 {bits}")
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise TypeError(f"seed 必须是 int，收到 {type(seed).__name__}")
        self._bits = bits
        self._seed = seed
        self._buckets = 2**bits
        self._registers = bytearray(self._buckets)
        self._digest = hashlib.blake2b(digest_size=8, key=_stable_payload(seed))
        self._lock = threading.Lock()

    @property
    def bits(self):
        """桶数指数：桶数是 2**bits。"""
        return self._bits

    @property
    def seed(self):
        """构造时用的散列种子。"""
        return self._seed

    def _hash(self, key):
        """把 key 规范化后散列成 64 位非负整数。"""
        from dedupkit.codec import _encode_key

        encoded = json.dumps(
            _encode_key(key), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        digest = self._digest.copy()
        digest.update(encoded)
        return int.from_bytes(digest.digest(), "big")

    def add(self, key):
        """记一个 key；类型约束与落盘一致（str/int/bool/bytes/tuple/None）。"""
        value = self._hash(key)
        index = value & (self._buckets - 1)
        remaining = value >> self._bits
        rank = 1
        while rank <= 64 - self._bits:
            if remaining & 1:
                break
            remaining >>= 1
            rank += 1
        with self._lock:
            if self._registers[index] < rank:
                self._registers[index] = rank

    def registers(self):
        """桶位内容的一份字节快照，供落盘与合并使用。"""
        with self._lock:
            return bytes(self._registers)

    @classmethod
    def _from_registers(cls, bits, seed, data):
        """按既有桶位重建一个估算器（落盘读回与 merge 内部使用）。"""
        sketch = cls(bits=bits, seed=seed)
        sketch._registers = bytearray(data)
        return sketch

    def count(self):
        """不同 key 数的估算值；空估算器返回 0.0。"""
        with self._lock:
            registers = bytes(self._registers)
        buckets = self._buckets
        zero = buckets - sum(1 for rank in registers if rank)
        if buckets == 16:
            alpha = 0.673
        elif buckets == 32:
            alpha = 0.697
        elif buckets == 64:
            alpha = 0.709
        else:
            alpha = 0.7213 / (1.0 + 1.079 / buckets)
        raw = alpha * buckets * buckets / sum(2.0 ** (-rank) for rank in registers)
        if zero:
            linear = buckets * math.log(buckets / zero)
            if linear <= 2.5 * buckets:
                return linear
            if linear < 4.0 * buckets:
                # 切换区做线性混合：LC 无偏高方差，raw 在这里已接近无偏，
                # 硬切换会在个别散列种子下冒尖，混合把尾部误差压平。
                weight = (linear / buckets - 2.5) / 1.5
                return (1.0 - weight) * linear + weight * raw
        return raw

    def merge(self, other):
        """返回 self 与 other 并集的新估算器；两边都不动。

        桶数与 seed 必须一致，否则没法逐桶取最大值，抛 ValueError。
        """
        if not isinstance(other, BucketSketch):
            raise TypeError(
                f"只能合并 BucketSketch，收到 {type(other).__name__}"
            )
        if other._bits != self._bits or other._seed != self._seed:
            raise ValueError(
                f"参数不一致: self(bits={self._bits}, seed={self._seed}) "
                f"vs other(bits={other._bits}, seed={other._seed})"
            )
        if other is self:
            # 合自己一遍等于没合；提前返回也避开非重入锁的自我死锁。
            with self._lock:
                return BucketSketch._from_registers(
                    self._bits, self._seed, bytes(self._registers)
                )
        first, second = (self, other) if id(self) <= id(other) else (other, self)
        with first._lock, second._lock:
            mine = self._registers
            theirs = other._registers
            merged = bytearray(
                mine[i] if mine[i] >= theirs[i] else theirs[i]
                for i in range(self._buckets)
            )
        return BucketSketch._from_registers(self._bits, self._seed, merged)
