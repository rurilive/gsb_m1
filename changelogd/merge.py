"""多条分叉时间线的字段变更合并。

分支就是普通的 ChangeLog：从同一基础版本分叉后各自 append，
merge 按字段并回一条结果线。同字段不同值交由 resolver 消解；
不同字段各归各。DELETE 表示删除字段：最终快照不再含该字段，
但删除动作与随后被修改的冲突都留在合并历史里可复盘。
"""

import time
from collections import namedtuple

from changelogd.changelog import ChangeLog


class _Marker:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return self._name


DELETE = _Marker("DELETE")
_MISSING = _Marker("MISSING")

# 参与消解的候选：来自哪条分支、取什么值、原始变更（含版本与 ts）。
Candidate = namedtuple("Candidate", ["branch", "value", "change"])

# 合并结果里的一条字段变更。sources 标注它来自哪些分支，
# winner 是赢家候选，originals 是各分支的原始记录。
MergedChange = namedtuple(
    "MergedChange",
    ["obj", "field", "value", "version", "ts", "sources", "winner", "originals"],
)

# 同字段撞车的账：赢家来源、被消解的输家、所用策略、最终取值。
Conflict = namedtuple(
    "Conflict",
    ["field", "winner", "losers", "resolver", "value", "version", "ts"],
)


def first_wins(candidates, base_value):
    """默认策略：按分支传入顺序，最靠前的赢；删除恒赢。"""
    for candidate in candidates:
        if candidate.value is DELETE:
            return candidate
    return candidates[0]


def latest_ts_wins(candidates, base_value):
    """按各分支最后一次改动的 ts，晚的赢；删除恒赢。"""
    for candidate in candidates:
        if candidate.value is DELETE:
            return candidate
    return max(candidates, key=lambda c: c.change.ts)


_BUILTIN_RESOLVERS = {
    "first-wins": first_wins,
    "latest-ts": latest_ts_wins,
}


class MergeResult:
    """一次合并的结果：带来源的合并记录、冲突账与最终快照。"""

    def __init__(self, obj, entries, conflicts, base_snapshot=None):
        self._obj = obj
        self._entries = list(entries)
        self._conflicts = list(conflicts)
        self._base_snapshot = dict(base_snapshot) if base_snapshot else None

    @property
    def obj(self):
        return self._obj

    def entries(self):
        """合并后的字段记录，按首次处理字段的顺序，返回新列表。"""
        return list(self._entries)

    def history(self):
        """合并结果全文（含 DELETE 记录），返回新列表。"""
        return list(self._entries)

    def conflicts(self):
        """所有发生过消解的字段冲突，返回新列表。"""
        return list(self._conflicts)

    def losers(self):
        """所有被消解掉的输家候选，跨冲突平铺，返回新列表。"""
        result = []
        for conflict in self._conflicts:
            result.extend(conflict.losers)
        return result

    def source_of(self, field):
        """某字段最终取值来自哪些分支；字段不存在或已删除时返回 ()。"""
        for entry in self._entries:
            if entry.field == field:
                if entry.value is DELETE:
                    return ()
                return tuple(entry.sources)
        return ()

    def snapshot(self, base_snapshot=None):
        """在基础快照上叠加合并记录得到最终快照，已删除字段不出现。"""
        if base_snapshot is None:
            base_snapshot = self._base_snapshot
        result = dict(base_snapshot) if base_snapshot else {}
        for entry in self._entries:
            if entry.value is DELETE:
                result.pop(entry.field, None)
            else:
                result[entry.field] = entry.value
        return result

    def commit(self, log, version=None):
        """把合并结果按字段各追加一条进 ChangeLog（DELETE 也照记）。"""
        for entry in self._entries:
            log.append(self._obj, entry.field, entry.value, version or entry.version)
        return log


def merge(
    obj,
    base_version,
    branches,
    *,
    base=None,
    version=None,
    clock=time.time,
    resolver=None,
):
    """把从 base_version 分叉出的多条分支合回一条结果线。

    branches 为 [(分支名, ChangeLog), ...]，顺序即默认消解约定的优先级，
    分支日志里只放分叉之后各自动的字段。version 默认 base_version + 1。
    clock 每字段调用一次，记到合并记录的 ts 上。resolver 可用内置
    字符串 "first-wins"（默认）或 "latest-ts"，也可传签名为
    resolver(candidates, base_value) 的自定义函数，返回赢家候选
    （Candidate、分支名字符串或候选下标均可）。
    """
    named = [(name, log) for name, log in branches]
    if len(named) < 2:
        raise ValueError("merge 至少需要两条分支")
    names = [name for name, _ in named]
    if len(set(names)) != len(names):
        raise ValueError("分支名必须唯一")

    if resolver is None:
        resolve = first_wins
    elif callable(resolver):
        resolve = resolver
    else:
        try:
            resolve = _BUILTIN_RESOLVERS[resolver]
        except KeyError:
            raise ValueError(f"未知消解策略: {resolver!r}")

    if version is None:
        version = base_version + 1
    base_snapshot = base.at(obj, base_version) if base is not None else {}

    entries = []
    conflicts = []
    for field in _collect_field_order(named, obj):
        candidates = _last_per_branch(named, obj, field)
        ts = clock()

        if _all_equal(candidates):
            winner = candidates[0]
            entries.append(
                MergedChange(
                    obj, field, winner.value, version, ts,
                    tuple(c.branch for c in candidates), winner, tuple(candidates),
                )
            )
            continue

        picked = resolve(list(candidates), base_snapshot.get(field, _MISSING))
        winner = _as_candidate(picked, candidates, names)
        losers = [c for c in candidates if c is not winner]

        entries.append(
            MergedChange(
                obj, field, winner.value, version, ts,
                (winner.branch,), winner, tuple(candidates),
            )
        )
        conflicts.append(
            Conflict(
                field, winner.branch, tuple(losers),
                resolve, winner.value, version, ts,
            )
        )

    return MergeResult(obj, entries, conflicts, base_snapshot)


def _entries_of(log, obj):
    if isinstance(log, MergeResult):
        return log.entries()
    return log.history(obj)


def _collect_field_order(named, obj):
    order = []
    seen = set()
    for _, log in named:
        for change in _entries_of(log, obj):
            if change.field not in seen:
                seen.add(change.field)
                order.append(change.field)
    return order


def _last_per_branch(named, obj, field):
    candidates = []
    for branch, log in named:
        last = None
        for change in _entries_of(log, obj):
            if change.field == field:
                last = change
        if last is not None:
            candidates.append(Candidate(branch, last.value, last))
    return candidates


def _all_equal(candidates):
    first = candidates[0]
    return all(
        candidate.value is first.value or candidate.value == first.value
        for candidate in candidates[1:]
    )


def _as_candidate(picked, candidates, names):
    if isinstance(picked, Candidate):
        if picked not in candidates:
            raise ValueError("resolver 返回了不属于本次冲突的候选")
        return picked
    if isinstance(picked, str):
        for candidate in candidates:
            if candidate.branch == picked:
                return candidate
        raise ValueError(f"resolver 返回了未知分支名: {picked!r}")
    if isinstance(picked, bool):
        raise ValueError(f"resolver 返回值无法识别: {picked!r}")
    if isinstance(picked, int):
        if 0 <= picked < len(candidates):
            return candidates[picked]
    raise ValueError(f"resolver 返回值无法识别: {picked!r}")
