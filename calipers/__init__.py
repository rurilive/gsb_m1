"""calipers: 纯标准库的平面点集几何度量工具包（当前为改造前基线）。

导出 CalipersKit 与全部异常类型。
"""

from .calipers import (
    CalipersKit,
    CalipersErro,
    PointSetErro,
    ClipErro,
)

__all__ = [
    "CalipersKit",
    "CalipersErro",
    "PointSetErro",
    "ClipErro",
]
