"""intervalx: 纯标准库的区间集合工具包（当前为改造前基线）。

导出 IntervalSet 与全部异常类型。
"""

from .interval import (
    IntervalSet,
    Erro,
    IntervalErro,
    TargetErro,
    IndexErro,
)

__all__ = [
    "IntervalSet",
    "Erro",
    "IntervalErro",
    "TargetErro",
    "IndexErro",
]
