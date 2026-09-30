"""winx: 定长滑动窗口统计工具集（当前为改造前的朴素基线）。

本包只提供一份朴素实现 WindowStats：每个窗口从头重扫一遍求极值、中位、
和与不同元素个数，窗口滑动即整段重算。纯标准库，无外部依赖。
"""

from winx.window import (
    InvalidSequenceError,
    InvalidWindowSizeError,
    WindowStats,
    WinxError,
    window_distinct,
    window_kth,
    window_max,
    window_median,
    window_min,
    window_rank,
    window_sum,
)

__all__ = [
    "InvalidSequenceError",
    "InvalidWindowSizeError",
    "WindowStats",
    "WinxError",
    "window_distinct",
    "window_kth",
    "window_max",
    "window_median",
    "window_min",
    "window_rank",
    "window_sum",
]
