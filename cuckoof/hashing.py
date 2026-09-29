"""哈希原语与指纹换算，cuckoof 各过滤器共用。

约定：

- digest 用 sha256 加固定盐，同一 key 跨进程、跨版本结果稳定，落盘格式
  与线上已有数据都依赖这一点，盐与算法别动；
- hash_pair 把摘要劈成两个 64 位无符号数，做双重哈希就是靠这一对；
- fingerprint 从摘要里取指定位宽的指纹，按掩码截断，位宽越短越省空间、
  也越容易撞；
- two_indexes 由指纹与两个哈希数算出两个候选桶下标，这是布谷鸟过滤器
  桶定位的口径，落盘格式与测试都依赖它。
"""

import hashlib

SALT = b"cuckoof.v1"


def digest(key):
    """key 的 32 字节摘要。str 按 utf-8 编码，bytes 与 bytearray 原样。"""
    if isinstance(key, (bytes, bytearray)):
        raw = bytes(key)
    else:
        raw = str(key).encode("utf-8")
    return hashlib.sha256(SALT + raw).digest()


def hash_pair(key, salt=0):
    """返回 (h1, h2)，各为一个 64 位无符号整数。salt 用来区分不同实例的展开。"""
    d = digest(key)
    h1 = int.from_bytes(d[:8], "big")
    h2 = int.from_bytes(d[8:16], "big")
    if salt:
        h1 = (h1 ^ (salt * 0x9E3779B97F4A7C15)) & ((1 << 64) - 1)
        h2 = (h2 ^ (salt * 0xC2B2AE3D27D4EB4F)) & ((1 << 64) - 1)
    return h1, h2


def fingerprint(key, bits):
    """取 bits 位指纹，返回 [1, 2**bits) 内的整数，指纹不为零。"""
    bits = int(bits)
    if bits < 1:
        raise ValueError("bits must be >= 1")
    d = digest(key)
    value = int.from_bytes(d[16:24], "big")
    return (value & ((1 << bits) - 1)) or 1


def two_indexes(fp, h1, h2, num_buckets):
    """由指纹与两个哈希数算出两个候选桶下标，落在 [0, num_buckets)。"""
    num_buckets = int(num_buckets)
    if num_buckets < 1:
        raise ValueError("num_buckets must be >= 1")
    i1 = h1 % num_buckets
    i2 = (i1 ^ (fp * 0x9E3779B97F4A7C15)) % num_buckets
    if i2 == i1:
        i2 = (i2 + 1) % num_buckets
    return i1, i2
