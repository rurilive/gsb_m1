"""hullx: 纯标准库的平面点集凸包工具包（当前为改造前基线）。

导出 HullKit 与全部异常类型。
"""

from .hull import (
    HullKit,
    HullErro,
    PointSetErro,
    RectErro,
)

__all__ = [
    "HullKit",
    "HullErro",
    "PointSetErro",
    "RectErro",
]
