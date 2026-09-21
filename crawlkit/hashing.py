"""哈希原语，crawlkit 各过滤器共用。

约定：

- digest 用 sha256 加固定盐，同一 key 跨进程、跨版本结果稳定，落盘格式
  和线上已写数据都依赖这一点，盐和算法别动；
- hash_pair 把摘要劈成两个 64 位无符号数，双重哈希就靠这一对；
- fingerprint 取固定位数指纹，返回值恒不为零，0 留作空槽哨兵，凡是要往
  槽位里填指纹的实现都得守住这条，否则空槽和真指纹分不开。
"""

import hashlib

SALT = b"crawlkit.v1"


def digest(key):
    """key 的 32 字节摘要。str 按 utf-8 编码，bytes 和 bytearray 原样。"""
    if isinstance(key, (bytes, bytearray)):
        raw = bytes(key)
    else:
        raw = str(key).encode("utf-8")
    return hashlib.sha256(SALT + raw).digest()


def hash_pair(key):
    """返回 (h1, h2)，各为一个 64 位无符号整数。"""
    d = digest(key)
    return int.from_bytes(d[:8], "big"), int.from_bytes(d[8:16], "big")


def bit_indexes(h1, h2, count, num_bits):
    """双重哈希展开 count 个位下标，逐个落在 [0, num_bits)。"""
    if count < 1:
        raise ValueError("count must be >= 1")
    if num_bits < 1:
        raise ValueError("num_bits must be >= 1")
    for i in range(count):
        yield (h1 + i * h2) % num_bits


def bucket_index(h, num_buckets):
    """把一个 64 位哈希折进 [0, num_buckets)。"""
    if num_buckets < 1:
        raise ValueError("num_buckets must be >= 1")
    return h % num_buckets


def fingerprint(h, fp_bits):
    """取 fp_bits 位指纹，结果落在 [1, (1 << fp_bits) - 1]，恒不为零。"""
    if fp_bits < 1:
        raise ValueError("fp_bits must be >= 1")
    return h % ((1 << fp_bits) - 1) + 1
