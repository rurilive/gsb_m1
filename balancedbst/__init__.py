"""balancedbst：自平衡有序二叉树的朴素基线包。

导出 BalancedBST 类与全部异常类型。基线只是一棵普通二叉搜索树：插入
按值大小递归下降、删除找中序后继替换、查找按值大小下降，不做任何旋转
与高度维护，有序插入时会退化成一条链。
"""

from .tree import (
    BalancedBST,
    BalancedBSTError,
    EmptyTreeError,
    KeyMissingError,
    ValueTypeError,
)

__all__ = [
    "BalancedBST",
    "BalancedBSTError",
    "EmptyTreeError",
    "KeyMissingError",
    "ValueTypeError",
]
