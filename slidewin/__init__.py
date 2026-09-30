"""slidewin: 纯标准库的滑动窗口与双指针统计工具包（当前为改造前基线）。

导出 WindowStats 与全部报告对象、异常类型。
"""

from .window import (
    WindowStats,
    SumReport,
    DistinctReport,
    SlideErro,
    SeqErro,
    ParamErro,
)

__all__ = [
    "WindowStats",
    "SumReport",
    "DistinctReport",
    "SlideErro",
    "SeqErro",
    "ParamErro",
]
