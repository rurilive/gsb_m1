"""digitcount: 纯标准库的区间按位计数工具包（当前为改造前基线）。

导出 IntervalCounter 与全部异常类型。
"""

from .count import (
    IntervalCounter,
    Erro,
    RangeErro,
    ValueErro,
    ParamErro,
    MAX_DIGITS,
    DEFAULT_BASE,
)

__all__ = [
    "IntervalCounter",
    "Erro",
    "RangeErro",
    "ValueErro",
    "ParamErro",
    "MAX_DIGITS",
    "DEFAULT_BASE",
]
