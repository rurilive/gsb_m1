"""哈希原语与最优参数换算，bloomchain 各布隆实现共用。

约定：

- digest 用 sha256 加固定盐，同一 key 跨进程、跨版本结果稳定，落盘格式
  与线上已有数据都依赖这一点，盐与算法别动；
- hash_pair 把摘要劈成两个 64 位无符号数，双重哈希展开就靠这一对，
  可选 salt 用来区分不同层的展开；
- bit_indexes 双重哈希展开出 count 个下标，逐个落在 [0, num_bits)；
- optimal_params 按期望元素数与目标误判率算最优位数与哈希次数；
- estimate_cardinality 由位数与置位数估已插入个数，线性计数法。

sizing 是旧口径别名，落盘与测试都还在用它，别删也别改行为。
"""

import hashlib
import math

SALT = b"bloomchain.v1"


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


def optimal_params(expected, fp_rate):
    """按期望元素数与目标误判率返回最优 (num_bits, num_hashes)。

    num_bits 取 -n * ln(p) / (ln2 的平方) 向上取整，下限 8；
    num_hashes 取 num_bits/n * ln2 四舍五入，下限 1。
    参数非法一律抛 ValueError。
    """
    if not isinstance(expected, int) or isinstance(expected, bool):
        raise ValueError("expected must be an int")
    if expected <= 0:
        raise ValueError("expected must be positive")
    if isinstance(fp_rate, bool) or not isinstance(fp_rate, (int, float)):
        raise ValueError("fp_rate must be a number")
    fp_rate = float(fp_rate)
    if not 0.0 < fp_rate < 1.0:
        raise ValueError("fp_rate must be in (0, 1)")
    ln2 = math.log(2)
    num_bits = max(8, int(math.ceil(-(expected * math.log(fp_rate)) / (ln2 * ln2))))
    num_hashes = max(1, int(round((num_bits / expected) * ln2)))
    return num_bits, num_hashes


def estimate_cardinality(num_bits, set_bits):
    """线性计数法：由位数与置位数估已插入元素个数，夹在 [0, num_bits]。"""
    num_bits = int(num_bits)
    set_bits = int(set_bits)
    if num_bits < 1:
        raise ValueError("num_bits must be >= 1")
    if set_bits < 0:
        set_bits = 0
    if set_bits > num_bits:
        set_bits = num_bits
    if set_bits == 0:
        return 0.0
    if set_bits >= num_bits:
        return float(num_bits)
    return round(-(num_bits / math.log(1.0 - set_bits / num_bits)), 3)


def sizing(capacity, fp_rate):
    """旧口径换算，等同 optimal_params(capacity, fp_rate)，保留兼容。"""
    return optimal_params(int(capacity), float(fp_rate))
