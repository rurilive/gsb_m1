"""三方合并的现状：只做两序列等值比较的一道薄封装。

仓库现在还没有编辑脚本，也没有基于基线的逐块合并。这里先把两段序列是否
完全一致、以及不一致时差在哪些下标报出来，作为后续三方合并的落脚点。
"""

from .diff import changes_only, diff, ensure_sequence
from .errors import MergeConflictError


def same_list(left, right):
    """两段序列逐一相等时返回 True。"""
    ensure_sequence(left, "left")
    ensure_sequence(right, "right")
    if len(left) != len(right):
        return False
    return all(a == b for a, b in zip(left, right))


def changed_indices(left, right):
    """列出两段序列取值不同的那些下标。"""
    return [change.index for change in changes_only(diff(left, right))]


def merge(base, ours, theirs):
    """三方合并的现状占位实现。

    还没有编辑脚本，无法逐块比对两侧改动，只能在两侧都与基线一致时给出
    基线本身；任一侧偏离基线就无从判断改动落点，直接报冲突。
    """
    ensure_sequence(base, "base")
    ensure_sequence(ours, "ours")
    ensure_sequence(theirs, "theirs")
    if same_list(ours, base) and same_list(theirs, base):
        return list(base)
    if same_list(ours, base):
        return list(theirs)
    if same_list(theirs, base):
        return list(ours)
    raise MergeConflictError("当前实现无法合并：两侧都与基线不同")


__all__ = ["changed_indices", "merge", "same_list"]