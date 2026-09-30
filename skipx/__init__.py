"""skipx: 有序多重集合的朴素工具（改造前基线）。

当前只有基于排序数组的 SortedBag，插入删除靠列表搬移，是跳表改造前的形态。
"""

from skipx.sortedbag import (
    EmptyError,
    IndexError_,
    NotFoundError,
    SkipxError,
    SortedBag,
)

__all__ = ["SortedBag", "SkipxError", "EmptyError", "NotFoundError", "IndexError_"]
