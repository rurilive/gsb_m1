"""subfam: 纯标准库的连续子段统计工具包（当前为改造前基线）。

导出 SubarrayStats 与全部报告对象、异常类型。
"""

from .stats import (
    SubarrayStats,
    SumReport,
    RangeReport,
    ProductReport,
    StatsErro,
    SeqErro,
    ParamErro,
)

__all__ = [
    "SubarrayStats",
    "SumReport",
    "RangeReport",
    "ProductReport",
    "StatsErro",
    "SeqErro",
    "ParamErro",
]
