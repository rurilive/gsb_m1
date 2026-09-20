"""intervaltree: 闭区间集合（增强二叉搜索树）。"""

from .errors import OverlapError
from .tree import IntervalTree

__all__ = ["IntervalTree", "OverlapError"]
