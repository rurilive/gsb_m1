"""多分支三方合并：base 为共同祖先，left/right 为两条分支的变更序列。

按 (obj, field) 对齐三方：只有一边动过的字段直接带走；两边最终值
不一致时交给消解策略挑赢家，输家记入冲突台账。合并结果可重放进
一个 ChangeLog 得到最终快照，每条变更都带来源标注。
"""

from collections import namedtuple

from .changelog import DELETED

# 合并结果里的一条变更：change 为原 Change 对象，origin 记来源
# （"base" / "left" / "right" / "resolved"）。
MergedChange = namedtuple("MergedChange", ["change", "origin"])

# 一次冲突：哪个对象的哪个字段，winner 为入选的 MergedChange，
# losers 为被消解掉的 MergedChange 元组（含各自来源）。
Conflict = namedtuple("Conflict", ["obj", "field", "winner", "losers"])


def resolve_newest(field, left, right):
    """默认策略：删除优先；否则 (version, ts) 较新者胜；完全打平取 right。"""
    if left.value is DELETED and right.value is not DELETED:
        return left
    if right.value is DELETED and left.value is not DELETED:
        return right
    if (left.version, left.ts) > (right.version, right.ts):
        return left
    return right


def resolve_left(field, left, right):
    """一律取 left。"""
    return left


def resolve_right(field, left, right):
    """一律取 right。"""
    return right


class MergeResult:
    """merge 的返回值：可重放的变更序列 + 冲突台账。

    changes: [MergedChange]，base 在前，分支变更按 (version, ts) 稳定排序。
    conflicts: [Conflict]，按字段首次出现的顺序。
    """

    def __init__(self, changes, conflicts):
        self.changes = changes
        self.conflicts = conflicts

    @property
    def losers(self):
        """所有被消解掉的变更（含来源），按冲突顺序。"""
        return [loser for conflict in self.conflicts for loser in conflict.losers]

    def apply_to(self, log):
        """把合并结果按序 append 进一个 ChangeLog，返回该 log。"""
        for merged in self.changes:
            change = merged.change
            log.append(change.obj, change.field, change.value, change.version)
        return log


def merge(base, left, right, resolve=resolve_newest):
    """三方合并，返回 MergeResult。base/left/right 均为 Change 序列（可跨对象）。

    分支是否"动过"某字段，看它在该字段上的最终值与 base 是否不同。
    两边都动了且最终值不同 -> resolve(field, left终值, right终值) 决定赢家，
    赢家一边在该字段上的整段变更入选，输家终值记入 Conflict；resolve 返回
    两边之外的 Change 时，该变更单独入选，origin 记为 "resolved"。
    """
    base = list(base)
    left = list(left)
    right = list(right)

    def finals(changes):
        out = {}
        for change in changes:
            out[(change.obj, change.field)] = change
        return out

    def grouped(changes):
        out = {}
        for change in changes:
            out.setdefault((change.obj, change.field), []).append(change)
        return out

    base_final = finals(base)
    left_final = finals(left)
    right_final = finals(right)
    left_by = grouped(left)
    right_by = grouped(right)

    changes = [MergedChange(change, "base") for change in base]
    branch_changes = []
    conflicts = []

    keys = dict.fromkeys(list(left_by) + list(right_by))
    for obj, field in keys:
        key = (obj, field)
        left_seq = left_by.get(key, [])
        right_seq = right_by.get(key, [])
        base_change = base_final.get(key)
        left_change = left_final.get(key)
        right_change = right_final.get(key)

        def touched(change):
            return change is not None and (
                base_change is None or change.value != base_change.value
            )

        left_touched = touched(left_change)
        right_touched = touched(right_change)

        if left_touched and right_touched:
            if left_change.value == right_change.value:
                branch_changes += [MergedChange(c, "left") for c in left_seq]
                continue
            winner = resolve(field, left_change, right_change)
            if winner is left_change:
                origin, seq = "left", left_seq
                losers = (MergedChange(right_change, "right"),)
            elif winner is right_change:
                origin, seq = "right", right_seq
                losers = (MergedChange(left_change, "left"),)
            else:
                origin, seq = "resolved", [winner]
                losers = (
                    MergedChange(left_change, "left"),
                    MergedChange(right_change, "right"),
                )
            branch_changes += [MergedChange(c, origin) for c in seq]
            conflicts.append(
                Conflict(obj, field, MergedChange(winner, origin), losers)
            )
        elif left_touched:
            branch_changes += [MergedChange(c, "left") for c in left_seq]
        elif right_touched:
            branch_changes += [MergedChange(c, "right") for c in right_seq]

    branch_changes.sort(key=lambda mc: (mc.change.version, mc.change.ts))
    changes.extend(branch_changes)
    return MergeResult(changes, conflicts)
