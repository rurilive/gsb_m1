"""lisx: 纯标准库的最长上升子序列工具包（当前为改造前基线）。

导出 LisKit 与全部异常类型。
"""

from .lis import (
    LisKit,
    LisErro,
    SeqErro,
    ModeErro,
)

__all__ = [
    "LisKit",
    "LisErro",
    "SeqErro",
    "ModeErro",
]
