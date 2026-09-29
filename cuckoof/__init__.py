"""cuckoof：布谷鸟过滤器落地前的朴素集合基线。

当前只有基于 dict 的 NaiveSet：add、contains、remove 精确且不扩容，
没有桶、没有指纹、也没有假阳性。指纹桶、删除安全、误判上界与扩容这批
能力都还没落地，等后续迭代补上。
"""

from .errors import CapacityError, CuckooError
from .hashing import digest, fingerprint, hash_pair, two_indexes
from .naive import NaiveSet
from .randomstate import RandomState

__all__ = [
    "CapacityError",
    "CuckooError",
    "NaiveSet",
    "RandomState",
    "digest",
    "fingerprint",
    "hash_pair",
    "two_indexes",
]