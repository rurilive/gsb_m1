"""按版本号记录字段变更的变更日志。

每个对象维护一串变更记录：append 追加，history 取全文，
at 把某一版本之前的变更叠成对象快照。纯标准库，无真实 IO。

分叉合并：fork 从某版本复制出一条分支，各自 append；
merge_branches 把各分支分叉点之后的字段最新值并排重放回一条线。
冲突（同字段两边值不同，含删除与修改）按策略消解，
默认"删除优先、否则按分支列出顺序取前者"。
"""

import time
from collections import namedtuple

# 一条字段变更：哪个对象的哪个字段，在哪个版本被改成了什么值。
Change = namedtuple("Change", ["obj", "field", "value", "version", "ts"])


class _Delete:
    """删除标记：字段取到该值表示已被删除，快照里不再出现。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "DELETE"


DELETE = _Delete()

# 合并候选：某条分支分叉点之后某字段的最后一次改动。
Candidate = namedtuple("Candidate", ["branch", "change"])
# 落进合并线的一条记录：change 为实际重放的 Change，branch 为来源分支，
# state 为 "winner"/"loser"（分叉前原有的记录没有标注）。
MergedEntry = namedtuple("MergedEntry", ["change", "branch", "state"])
# 一次字段冲突的账：字段、各方候选、赢/输分支名。
Conflict = namedtuple("Conflict", ["field", "candidates", "winner", "losers"])


class MergeReport:
    """一次合并的对账结果。

    merged 按落线顺序列出每条重放记录（含输家），
    conflicts 按消解顺序列出每个冲突字段。
    """

    def __init__(self, version, merged, conflicts):
        self.version = version  # 合并线最后一条记录的版本
        self.merged = merged
        self.conflicts = conflicts

    def losers(self):
        """被消解掉的输家记录（MergedEntry），按落线顺序。"""
        return [entry for entry in self.merged if entry.state == "loser"]


class ChangeLog:
    """单条时间线上的字段变更日志。

    clock: 返回当前时刻的可调用对象，默认 time.time，测试可注入。
    version 由调用方给定，本包不校验它是否单调。
    """

    def __init__(self, clock=time.time):
        self._clock = clock
        self._entries = {}  # obj -> [Change]，保持 append 顺序
        self._annotations = {}  # obj -> [分支名 或 None]，与 _entries 对齐
        self._name = "main"

    def append(self, obj, field, value, version):
        """给 obj 的 field 记一条变更，返回新记录。"""
        return self._record(obj, field, value, version, self._clock())

    def _record(self, obj, field, value, version, ts, branch=None):
        change = Change(obj, field, value, version, ts)
        self._entries.setdefault(obj, []).append(change)
        self._annotations.setdefault(obj, []).append(branch)
        return change

    def fork(self, base_version, name):
        """从 base_version 复制一条名为 name 的分支，返回新 ChangeLog。

        只保留 version 不超过 base_version 的记录；之后在分支上各自
        append，版本号各自独立。新分支沿用同一时钟。
        """
        branch = ChangeLog(clock=self._clock)
        branch._name = name
        for obj in self.objects():
            for change, note in zip(self._entries[obj], self._annotations[obj]):
                if change.version <= base_version:
                    branch._record(
                        obj, change.field, change.value, change.version,
                        change.ts, note,
                    )
        return branch

    def provenance(self, obj):
        """与 history 对齐的来源标注列表：分支名或 None（分叉前原有）。

        返回新列表，长度与 history(obj) 相同，按相同顺序排列。
        """
        return list(self._annotations.get(obj, ()))

    def history(self, obj):
        """obj 的全部变更，按 append 顺序，返回新列表。"""
        return list(self._entries.get(obj, ()))

    def at(self, obj, version):
        """重建 obj 在给定版本的快照。

        每个字段取 append 顺序里最后一条 version 不超过给定值的变更；
        在此之前该字段没有变更则不出现。返回新 dict。
        """
        snapshot = {}
        for change in self._entries.get(obj, ()):
            if change.version <= version:
                if change.value is DELETE:
                    snapshot.pop(change.field, None)
                    continue
                snapshot[change.field] = change.value
        return snapshot

    def objects(self):
        """出现过的对象名，按首次 append 顺序。"""
        return list(self._entries)

    def merge_branches(self, base_version, branches, resolver="delete-wins",
                       clock=None):
        """把 branches（按列出顺序）分叉点之后的改动合回本日志。

        branches: [(分支名, ChangeLog), ...]，第一个是默认赢家顺序上的
        首位（通常是主线分支）。每个字段取各分支在 base_version 之后
        的最后一次改动：值相同（含都删除）只留一份；值不同构成冲突，
        交给 resolver 消解。

        resolver: 预设名或可调用对象。预设：
          "delete-wins"（默认）：删除先赢，否则取分支列出顺序靠前者；
          "first-wins"：一律取分支列出顺序靠前者；
          "latest-wins"：取列出顺序靠后者；
          "latest-ts-wins"：取改动时刻（ts）最晚者，并列取前者。
        自定义签名为 resolver(field, candidates, base_version)，
        candidates 是按分支列出顺序排好的 Candidate 列表，
        返回中选的 Candidate（或其分支名 / 下标）。

        合并记录逐条重放，每条的版本与 ts 都取自合并时钟（注入时钟
        可断言）；输家先落、赢家后落，history 看得见，at 折叠后只剩
        赢家口径。返回 MergeReport。
        """
        merge_clock = clock if clock is not None else self._clock
        resolve = _build_resolver(resolver)

        # per_obj_tips: obj -> [{field: Candidate}]，与 branches 顺序对齐
        per_obj_tips = {}
        objects = []
        for index, (branch_name, branch_log) in enumerate(branches):
            for change in branch_log._entries_iter_after(base_version):
                if change.obj not in per_obj_tips:
                    per_obj_tips[change.obj] = [dict() for _ in branches]
                    objects.append(change.obj)
                per_obj_tips[change.obj][index][change.field] = Candidate(
                    branch_name, change)

        merged = []
        conflicts = []
        last_version = base_version
        for obj in objects:
            tips = per_obj_tips[obj]
            field_names = set()
            for fields in tips:
                field_names.update(fields)
            for field in sorted(field_names):
                candidates = [
                    fields[field]
                    for fields in tips
                    if field in fields
                ]
                if _same_value(candidates[0].change.value,
                               [c.change.value for c in candidates[1:]]):
                    winner = candidates[0]
                    losers = []
                else:
                    winner = resolve(field, list(candidates), base_version)
                    winner = _select(winner, candidates)
                    losers = [c for c in candidates if c is not winner]
                    conflicts.append(Conflict(
                        field, list(candidates), winner.branch,
                        [c.branch for c in losers],
                    ))
                # 输家先落线，赢家最后落：at 折叠后赢家生效，
                # history 里两边的中间经过都留痕。
                ordered = losers + [winner]
                states = ["loser"] * len(losers) + ["winner"]
                for candidate, state in zip(ordered, states):
                    tick = merge_clock()
                    change = self._record(
                        obj, field, candidate.change.value, tick, tick,
                        candidate.branch,
                    )
                    merged.append(MergedEntry(
                        change, candidate.branch, state))
                    last_version = tick

        return MergeReport(last_version, merged, conflicts)

    def _entries_iter_after(self, base_version):
        """本日志中 version 大于 base_version 的记录，按对象、再按 append
        顺序产出。"""
        for obj in self.objects():
            for change in self._entries[obj]:
                if change.version > base_version:
                    yield change


_PRESETS = {}


def _preset(name):
    def register(func):
        _PRESETS[name] = func
        return func
    return register


@_preset("delete-wins")
def _resolve_delete_wins(field, candidates, base_version):
    for candidate in candidates:
        if candidate.change.value is DELETE:
            return candidate
    return candidates[0]


@_preset("first-wins")
def _resolve_first_wins(field, candidates, base_version):
    return candidates[0]


@_preset("latest-wins")
def _resolve_latest_wins(field, candidates, base_version):
    return candidates[-1]


@_preset("latest-ts-wins")
def _resolve_latest_ts_wins(field, candidates, base_version):
    winner = candidates[0]
    for candidate in candidates[1:]:
        if candidate.change.ts > winner.change.ts:
            winner = candidate
    return winner


def _build_resolver(resolver):
    if isinstance(resolver, str):
        try:
            return _PRESETS[resolver]
        except KeyError:
            raise ValueError(
                f"未知消解策略 {resolver!r}，可选：{sorted(_PRESETS)}"
            ) from None
    return resolver


def _select(choice, candidates):
    if isinstance(choice, Candidate):
        return choice
    if isinstance(choice, int):
        return candidates[choice]
    for candidate in candidates:
        if candidate.branch == choice:
            return candidate
    raise ValueError(f"消解结果 {choice!r} 不在候选分支中")


def _same_value(value, others):
    for other in others:
        if value is DELETE or other is DELETE:
            if value is not other:
                return False
        elif value != other:
            return False
    return True
