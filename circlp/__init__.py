"""circlp: 纯标准库的环形序列最优化工具包（当前为改造前基线）。

导出 CircularOpt 与全部异常类型。
"""

from .circular import (
    CircularOpt,
    Erro,
    ValueErro,
    IndexErro,
    ChooseErro,
    MAX_ENUM_LEN,
)

__all__ = [
    "CircularOpt",
    "Erro",
    "ValueErro",
    "IndexErro",
    "ChooseErro",
    "MAX_ENUM_LEN",
]
