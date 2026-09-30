"""waveletx: 区间查询工具包（纯标准库，无外部依赖）。

现有实现只有一条朴素路径：对每个查询把区间整段取出排序或者逐个扫描，
提供区间第 k 小、排名、不超过某值的个数、某值出现次数四项能力，
不提供小波树，也没有第二条独立做法可互相印证，更不暴露访问规模。
"""

from .naive import (
    InvalidRangeError,
    KthOutOfRangeError,
    NaiveRangeIndex,
    WaveletXError,
    check_range,
    count_equal,
    count_leq,
    kth_smallest,
    range_rank,
)

__all__ = [
    "InvalidRangeError",
    "KthOutOfRangeError",
    "NaiveRangeIndex",
    "WaveletXError",
    "check_range",
    "count_equal",
    "count_leq",
    "kth_smallest",
    "range_rank",
]
