"""binanswer: 纯标准库的最优化可行性工具包（当前为改造前基线）。

导出 BinaryAnswerKit 与全部异常类型。
"""

from .binanswer import (
    BinaryAnswerKit,
    BinErro,
    InputErro,
    UnsatErro,
    BackendErro,
)

__all__ = [
    "BinaryAnswerKit",
    "BinErro",
    "InputErro",
    "UnsatErro",
    "BackendErro",
]
