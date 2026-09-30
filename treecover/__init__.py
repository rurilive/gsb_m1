"""treecover: 树上覆盖工具的朴素基线（改造前）。

对外只暴露 Tree 与那一层朴素的子集枚举求解，以及错误基类。
"""

from .tree import (
    CoverError,
    EmptyTreeError,
    NotATreeError,
    Tree,
    enumerate_subsets,
    is_dominating_set,
    is_independent_set,
    is_vertex_cover,
    max_independent_set,
    max_weight_independent_set,
    min_dominating_set,
    min_vertex_cover,
    subset_check_count,
    weighted_min_dominating_set,
)

__all__ = [
    "Tree",
    "CoverError",
    "NotATreeError",
    "EmptyTreeError",
    "enumerate_subsets",
    "is_dominating_set",
    "is_vertex_cover",
    "is_independent_set",
    "min_dominating_set",
    "min_vertex_cover",
    "max_independent_set",
    "weighted_min_dominating_set",
    "max_weight_independent_set",
    "subset_check_count",
]
