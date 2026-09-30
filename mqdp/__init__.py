"""mqdp: 窗口约束动态规划工具集（当前为改造前的朴素基线）。

本包只提供一份朴素实现 WindowDP：对一维状态转移，每个前缀把允许前驱区间里
每个前驱挨个看一遍取转移值的最优，不做任何优化，规模一大就慢但结果对。
纯标准库，无外部依赖。
"""

from mqdp.tables import (
    DataErro,
    CoefErro,
    MAX_POLICY,
    MIN_POLICY,
    MqdpErro,
    WindowDP,
    WindowErro,
)

__all__ = [
    "CoefErro",
    "DataErro",
    "MAX_POLICY",
    "MIN_POLICY",
    "MqdpErro",
    "WindowDP",
    "WindowErro",
]
