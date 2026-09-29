"""bloomchain：可扩展布隆过滤器落地前的定长基线。

当前只有一层定长位数组的 NaiveBloomFilter：add、contains、len 与 stats
可用，位数组只置位不清位，没有分层扩展、没有基数估计、没有序列化、
也没有合并。分层扩展、误判率上界、基数估计与落盘这批能力都还没落地，
等后续迭代补上。
"""

from .errors import BloomError, CapacityError
from .hashing import (
    bit_indexes,
    digest,
    estimate_cardinality,
    hash_pair,
    optimal_params,
    sizing,
)
from .naive import NaiveBloomFilter
from .randomstate import RandomState

__all__ = [
    "BloomError",
    "CapacityError",
    "NaiveBloomFilter",
    "RandomState",
    "bit_indexes",
    "digest",
    "estimate_cardinality",
    "hash_pair",
    "optimal_params",
    "sizing",
]
