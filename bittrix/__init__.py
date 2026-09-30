"""bittrix: 整数位操作的朴素实现。

当前只有一条路：求一的个数、最低位一、最高位一、二的幂判定、二进制逆序、公
共前缀、相邻位判定、批量每位置位计数，全靠对位串逐字符比对或对整数逐位右
移。见 bittrix.naive，位技巧做法见任务描述。
"""

from bittrix.naive import (
    BitError,
    BitTools,
    Erro,
    all_adjacent_pairs_differ,
    bit_position_counts,
    common_prefix_length,
    gray_adjacent_one_bit,
    has_adjacent_alternating,
    highest_set_bit,
    interleave_check,
    is_power_of_two,
    lowest_set_bit,
    popcount_loop,
    popcount_str,
    reverse_bits,
)

__all__ = [
    "BitError",
    "BitTools",
    "Erro",
    "all_adjacent_pairs_differ",
    "bit_position_counts",
    "common_prefix_length",
    "gray_adjacent_one_bit",
    "has_adjacent_alternating",
    "highest_set_bit",
    "interleave_check",
    "is_power_of_two",
    "lowest_set_bit",
    "popcount_loop",
    "popcount_str",
    "reverse_bits",
]
