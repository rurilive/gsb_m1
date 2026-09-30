"""invx: 整数序列上的逆序统计工具集（当前为基线朴素实现）。"""

from invx.inv import (
    EmptySequenceError,
    InversionError,
    InvalidInputError,
    SequenceTooShortError,
    Values,
    count_equal_pairs,
    count_inversions,
    count_ordered_pairs,
    distinct_count,
    has_duplicates,
    kth_smallest,
    max_inversions,
    rank_of,
)

__all__ = [
    "EmptySequenceError",
    "InversionError",
    "InvalidInputError",
    "SequenceTooShortError",
    "Values",
    "count_equal_pairs",
    "count_inversions",
    "count_strict_inversions",
    "count_ordered_pairs",
    "distinct_count",
    "has_duplicates",
    "kth_smallest",
    "max_inversions",
    "rank_of",
]
