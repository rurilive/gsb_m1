"""diffx: 数组区间修改与查询工具包（当前为基线朴素实现）。"""

from diffx.array import (
    DiffArray,
    DiffError,
    DiffMatrix,
    InvalidIndexError,
    InvalidMatrixError,
    InvalidRangeError,
    InvalidShapesError,
    InvalidSizeError,
    elementwise_add,
    elementwise_equal,
    flatten,
)

__all__ = [
    "DiffArray",
    "DiffError",
    "DiffMatrix",
    "InvalidIndexError",
    "InvalidMatrixError",
    "InvalidRangeError",
    "InvalidShapesError",
    "InvalidSizeError",
    "elementwise_add",
    "elementwise_equal",
    "flatten",
]
