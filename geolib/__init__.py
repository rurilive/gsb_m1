"""geolib: 纯标准库的二维几何索引工具包。

当前只提供朴素线性扫描的矩形索引 FlatIndex。
"""

from geolib.spatial import GeoError, RectError, FlatIndex, rect_of

__all__ = ["GeoError", "RectError", "FlatIndex", "rect_of"]
