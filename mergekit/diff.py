"""双向比较：逐位比对两段序列，列出相等、替换、新增与删除的位置。

这是仓库的现状实现，只做最朴素的一层：按下标对齐后逐位比较，长度不等的
尾巴整体记成删除或新增。它不计算编辑脚本，也不做三方合并，只负责把两段
序列哪里不一样、差在哪个下标如实报出来。
"""

from collections import namedtuple

from .errors import DiffError

# 变化种类标记。
EQUAL = "equal"
REPLACE = "replace"
ADD = "add"
REMOVE = "remove"

# 一条变化记录：种类、下标，以及参与比较的左右两侧取值。
# 不参与某侧的变化（新增的 left、删除的 right）该侧取 None。
Change = namedtuple("Change", "kind index left right")

_KINDS = (EQUAL, REPLACE, ADD, REMOVE)


def ensure_sequence(value, name):
    """校验入参是一段可逐位比较的序列。

    接受 list 与 tuple；字符串、字典、None 以及其它类型一律拒绝，避免把
    一字长的字符串或键序列当成带下标的元素序列误用。
    """
    if isinstance(value, (list, tuple)):
        return value
    raise DiffError("参数 %s 必须是 list 或 tuple，收到 %r" % (name, type(value).__name__))


def diff(left, right):
    """逐位比较两段序列，返回变化记录组成的列表。

    下标对齐后逐位比较：取值相等记 equal，不等记 replace。较长的尾巴按
    方向记成 remove（左侧独有）或 add（右侧独有）。入参不被改写。
    """
    ensure_sequence(left, "left")
    ensure_sequence(right, "right")

    changes = []
    common = min(len(left), len(right))
    for index in range(common):
        a, b = left[index], right[index]
        if a == b:
            changes.append(Change(EQUAL, index, a, b))
        else:
            changes.append(Change(REPLACE, index, a, b))

    if len(left) > common:
        for index in range(common, len(left)):
            changes.append(Change(REMOVE, index, left[index], None))
    else:
        for index in range(common, len(right)):
            changes.append(Change(ADD, index, None, right[index]))

    return changes


def changes_only(changes):
    """从变化记录里过滤掉 equal，只留下真正有改动的部分。"""
    return [change for change in changes if change.kind != EQUAL]


def has_changes(changes):
    """变化记录里是否存在非 equal 的项。"""
    return any(change.kind != EQUAL for change in changes)


__all__ = [
    "ADD",
    "Change",
    "EQUAL",
    "REMOVE",
    "REPLACE",
    "changes_only",
    "diff",
    "ensure_sequence",
    "has_changes",
]
