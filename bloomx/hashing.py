"""哈希原语与定容参数换算，bloomx 各过滤器共用。

约定：

- digest 用 sha256 加固定盐，同一 key 跨进程、跨版本结果稳定，落盘格式
  与线上已写数据都依赖这一点，盐与算法别动；
- hash_pair 把摘要劈成两个 64 位无符号数，双重哈希就靠这一对；
- bit_indexes 做双重哈希展开，逐个落在给定位数内；
- sizing 按容量与目标误判率算位数与哈希个数，各过滤器口径一致。
"""

import hashlib
import math

SALT = b"bloomx.v1"


def digest(key):
    """key 的 32 字节摘要。str 按 utf-8 编码，bytes 与 bytearray 原样。"""
    if isinstance(key, (bytes, bytearray)):
        raw = bytes(key)
    else:
        raw = str(key).encode("utf-8")
    return hashlib.sha256(SALT + raw).digest()


def hash_pair(key, salt=0):
    """返回 (h1, h2)，各为一个 64 位无符号整数。salt 用来区分不同层的展开。"""
    d = digest(key)
    h1 = int.from_bytes(d[:8], "big")
    h2 = int.from_bytes(d[8:16], "big")
    if salt:
        h1 = (h1 ^ (salt * 0x9E3779B97F4A7C15)) & ((1 << 64) - 1)
        h2 = (h2 ^ (salt * 0xC2B2AE3D27D4EB4F)) & ((1 << 64) - 1)
    return h1, h2


def bit_indexes(h1, h2, count, num_bits):
    """双重哈希展开 count 个下标，逐个落在 [0, num_bits)。"""
    if count < 1:
        raise ValueError("count must be >= 1")
    if num_bits < 1:
        raise ValueError("num_bits must be >= 1")
    for i in range(count):
        yield (h1 + i * h2) % num_bits


def sizing(capacity, fp_rate):
    """按容量与目标误判率返回 (num_bits, num_hashes)。"""
    capacity = int(capacity)
    if capacity <= 0:
        raise ValueError("capacity must be positive")
    fp_rate = float(fp_rate)
    if not 0.0 < fp_rate < 1.0:
        raise ValueError("fp_rate must be in (0, 1)")
    ln2 = math.log(2)
    num_bits = max(8, int(math.ceil(-(capacity * math.log(fp_rate)) / (ln2 * ln2))))
    num_hashes = max(1, int(round((num_bits / capacity) * ln2)))
    return num_bits, num_hashes
