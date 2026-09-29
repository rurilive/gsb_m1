"""geox: 纯标准库的平面计算几何工具包（当前为改造前基线）。

导出 PlanarGeom 与全部异常类型。
"""

from .geom import (
    PlanarGeom,
    GeomError,
    PointSetError,
    SegmentError,
    PolygonError,
)

__all__ = [
    "PlanarGeom",
    "GeomError",
    "PointSetError",
    "SegmentError",
    "PolygonError",
]
