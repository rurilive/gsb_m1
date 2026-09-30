"""satx：朴素二元可满足性工具（改造前基线）。

提供 TwoSat 类，管一组布尔变量（从一编号）与若干二元的或约束，约束之间按
合取叠加。文字用带符号整数表示，正数取真、负数取反。当前判定可满足性、
给出方案、取某变量取值、统计满足的约束条数，全部靠把全部变量取值的组合
逐一枚举验证，变量一多组合数就指数爆炸，但结果正确。

以强连通分量为核心的蕴含图工具集见任务描述。
"""

from .twosat import (
    InvalidAssignmentError,
    InvalidLiteralError,
    SatError,
    TwoSat,
)

__all__ = [
    "TwoSat",
    "SatError",
    "InvalidLiteralError",
    "InvalidAssignmentError",
]
