"""kdtree: 静态点集上的范围查询与最近邻查询。

当前只提供基于线性扫描的裸函数，作为 k 维树改造前的朴素基线。
所有坐标为整数，比较与距离都用整数完成，不碰浮点。
"""

from kdtree.scan import (
    assert_points,
    inf_norm_sq,
    nearest,
    points_in_box,
)

__all__ = [
    "assert_points",
    "inf_norm_sq",
    "nearest",
    "points_in_box",
]
