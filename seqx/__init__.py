"""seqx: 序列上的区间操作工具集（当前为基线朴素实现）。"""

from seqx.seq import (
    EmptySequenceError,
    IndexOutOfRangeError,
    InvalidRangeError,
    Seq,
    SeqError,
    ValueRangeError,
    replay,
)

__all__ = [
    "EmptySequenceError",
    "IndexOutOfRangeError",
    "InvalidRangeError",
    "Seq",
    "SeqError",
    "ValueRangeError",
    "replay",
]
