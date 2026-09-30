"""slopex: 划分型动态规划工具集（当前为改造前的平方枚举基线）。

本包只提供一份朴素实现 SegmentPlanner：对一族把序列前若干项切成若干
连续段、让累计代价取最优的划分问题，用双重循环枚举最后一段的起点求
最优，规模一大就慢但结果对。纯标准库，无外部依赖。
"""

from slopex.quadratic import (
    INFINITY,
    InvalidPolicyError,
    InvalidSequenceError,
    InvalidWeightError,
    SegmentPlanner,
    SlopexError,
)

__all__ = [
    "INFINITY",
    "InvalidPolicyError",
    "InvalidSequenceError",
    "InvalidWeightError",
    "SegmentPlanner",
    "SlopexError",
]
