"""permorder: 排列生成与字典序的朴素求解器。

现状实现全部走递归枚举加排序：求下一个排列时先把全部不重复排列枚举排序再取
相邻那条；求第几个排列与按名次反查时同样先枚举全部再按下标或位置取值；判断
一个序列是不是另一个的排列时把两边各自排序后逐位比较。元素一多枚举的排列数
就按阶乘量级膨胀，但结果正确、口径固定。
"""

from permorder.core import (
    OutOfRangeError,
    PermOrder,
    PermOrderError,
    TypeMismatchError,
    UnsortedBasisError,
)

__all__ = [
    "OutOfRangeError",
    "PermOrder",
    "PermOrderError",
    "TypeMismatchError",
    "UnsortedBasisError",
]
