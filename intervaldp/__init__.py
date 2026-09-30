"""intervaldp: 纯标准库的区间划分与括号匹配工具包（当前为改造前基线）。

导出 IntervalKit 与全部异常类型。
"""

from .interval import (
    IntervalKit,
    IntervalErro,
    TextErro,
    StoneErro,
    CostErro,
)

__all__ = [
    "IntervalKit",
    "IntervalErro",
    "TextErro",
    "StoneErro",
    "CostErro",
]
