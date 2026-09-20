"""多分支分叉与合并。

一条基准日志 base 在某个版本分叉出若干分支（各自也是 ChangeLog，
只记分叉之后的改动），merge 把分支按字段合回一条日志：

- 只有一条分支动过的字段直接并入；
- 多条分支动过且最终值相同，视为同一改动，来源记全部命中分支；
- 最终值不同则交给 resolver 挑赢家，输家进 conflicts 记账；
- DELETE 是墓碑：删掉的字段就算之后又被改，快照里也不再出现，
  但中间改动仍留在历史里。

纯标准库，无真实 IO。
"""

from collections import namedtuple

from changelogd.changelog import Change, ChangeLog


class _Deleted:
    """字段被删除的墓碑标记，单例。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "DELETE"


# 墓碑值：append(obj, field, DELETE, version) 表示该字段在该版本被删除。
DELETE = _Deleted()

# 一条分支：名字 + 分叉后自己记的变更日志。
Branch = namedtuple("Branch", ["name", "log"])

# 一条并入后的变更：Change 五字段之外再带来源分支与合并前的原记录。
MergedChange = namedtuple(
    "MergedChange",
    ["obj", "field", "value", "version", "ts", "sources", "origin"],
)

# 一次同字段撞车的账目：字段、被选的赢家 Candidate、输家 Candidate 列表。
Conflict = namedtuple("Conflict", ["field", "winner", "losers"])

# 分支上某字段的最终改动候选：branch 为来源分支，change 为该分支上
# 这个字段的最后一条原记录（自定义消解函数按这两个属性取值）。
Candidate = namedtuple("Candidate", ["branch", "change"])


def fork(base, name, clock=None):
    """从 base 分出一条空分支，返回 Branch。"""
    return Branch(name, ChangeLog(clock=clock if clock is not None else base._clock))


def last_write_wins(field, candidates):
    """默认消解：墓碑优先（删了就不复活），否则取最新改动，平手按分支名。"""
    deleted = [c for c in candidates if c.change.value is DELETE]
    pool = deleted if deleted else candidates
    return min(pool, key=lambda c: (-c.change.ts, c.branch.name))


def prefer_branch(branch_name):
    """生成“总挑指定分支”的消解函数；该分支没碰该字段时退回默认策略。"""

    def _resolve(field, candidates):
        preferred = [c for c in candidates if c.branch.name == branch_name]
        if preferred:
            return last_write_wins(field, preferred)
        return last_write_wins(field, candidates)

    return _resolve


RESOLVERS = {
    "last-write-wins": last_write_wins,
}


class MergeResult:
    """合并产物：一条可读历史的 ChangeLog 外加来源与冲突账目。"""

    def __init__(self, log, merged, origins, conflicts):
        self._log = log
        self._merged = merged  # Change(并入后) -> MergedChange
        self._origins = origins  # Change -> [分支名]
        self._conflicts = conflicts  # obj -> [Conflict]

    def log(self):
        """合并后的 ChangeLog，沿用 append/history/at。"""
        return self._log

    def history(self, obj):
        """合并后全文，每条为带来源标注的 MergedChange。"""
        return [self._merged[c] for c in self._log.history(obj)]

    def origin(self, change):
        """某条并入记录来自哪些分支；基准原文返回空列表。"""
        return list(self._origins.get(change, ()))

    def conflicts(self, obj):
        """obj 被消解过的撞车账目，按字段合并顺序，返回新列表。"""
        return list(self._conflicts.get(obj, ()))

    def losers(self, obj):
        """所有被消解掉的输家原记录，跨字段拼接，返回新列表。"""
        out = []
        for conflict in self._conflicts.get(obj, ()):
            out.extend(candidate.change for candidate in conflict.losers)
        return out

    def at(self, obj, version=None):
        """合并后版本的快照；给定 version 则重建该版本（折叠墓碑）。"""
        cap = version if version is not None else 1 << 62
        snapshot = self._log.at(obj, cap)
        return {field: value for field, value in snapshot.items() if value is not DELETE}


def _resolve(resolver):
    if resolver is None:
        return last_write_wins
    if isinstance(resolver, str):
        return RESOLVERS[resolver]
    return resolver


def merge(obj, base, branches, base_version, resolver=None, clock=None):
    """把分叉自 base 同一 base_version 的若干分支合回一条线。

    resolver 见 README「实现说明」；clock 为合并记录的时钟，默认沿用
    base 的时钟。返回 MergeResult。
    """
    resolve = _resolve(resolver)
    if clock is None:
        clock = base._clock

    if not branches:
        raise ValueError("merge 需要至少一条分支")
    names = [branch.name for branch in branches]
    if len(names) != len(set(names)):
        raise ValueError("分支名必须唯一")

    merged = {}
    origins = {}
    conflicts_by_obj = {}

    result_log = ChangeLog(clock=clock)
    for change in base.history(obj):
        if change.version <= base_version:
            seeded = Change(obj, change.field, change.value, change.version, change.ts)
            result_log._entries.setdefault(obj, []).append(seeded)
            merged[seeded] = MergedChange(
                obj, change.field, change.value, change.version, change.ts,
                [], change,
            )

    # 收集每个字段在每条分支上的最后一条改动（分支按名字排序，保证稳定）。
    fields = {}
    for branch in sorted(branches, key=lambda b: b.name):
        latest = {}
        for change in branch.log.history(obj):
            latest[change.field] = change
        for field, change in latest.items():
            fields.setdefault(field, []).append(Candidate(branch, change))

    # 每个字段先选出赢家与输家；赢家再按合并时刻排队拿新版本号。
    # 每项：(排队时刻, 赢家候选, 命中候选, 输家候选, 是否撞车)
    winners = []
    for field, candidates in fields.items():
        candidates = sorted(candidates, key=lambda c: c.branch.name)
        if len(candidates) > 1:
            agreed = all(
                c.change.value is candidates[0].change.value
                or c.change.value == candidates[0].change.value
                for c in candidates[1:]
            )
            if agreed:
                queue_ts = min(c.change.ts for c in candidates)
                winners.append(
                    (queue_ts, candidates[0], list(candidates), [], False)
                )
                continue
        picked = resolve(field, list(candidates))
        chosen = picked if isinstance(picked, Candidate) else next(
            c for c in candidates if c.change is picked
        )
        chosen_set = [c for c in candidates if c.change is chosen.change]
        loser_candidates = [c for c in candidates if c.change is not chosen.change]
        winners.append((
            chosen.change.ts, chosen, chosen_set, loser_candidates,
            len(candidates) > 1,
        ))

    order = sorted(
        range(len(winners)),
        key=lambda i: (winners[i][0], winners[i][1].branch.name),
    )
    next_version = base_version
    for index in order:
        _, winner, chosen_candidates, loser_candidates, clashed = winners[index]
        change = winner.change
        # 墓碑赢了时，输家的改动按分支顺序也落进历史，再落墓碑：
        # 快照只看到字段消失，历史却看得见“改过又被删”这一段。
        if clashed and change.value is DELETE:
            ordered_losers = sorted(
                loser_candidates, key=lambda c: (c.change.ts, c.branch.name)
            )
            for loser in ordered_losers:
                next_version += 1
                buried = result_log.append(
                    obj, loser.change.field, loser.change.value, next_version
                )
                sources = [loser.branch.name]
                origins[buried] = sources
                merged[buried] = MergedChange(
                    obj, loser.change.field, loser.change.value, next_version,
                    buried.ts, sources, loser.change,
                )
        next_version += 1
        merged_change = result_log.append(obj, change.field, change.value, next_version)
        sources = [c.branch.name for c in sorted(
            chosen_candidates, key=lambda c: c.branch.name
        )]
        merged[merged_change] = MergedChange(
            obj, change.field, change.value, next_version, merged_change.ts,
            sources, change,
        )
        origins[merged_change] = sources
        if clashed and loser_candidates:
            conflicts_by_obj.setdefault(obj, []).append(
                Conflict(change.field, winner, list(loser_candidates))
            )

    return MergeResult(result_log, merged, origins, conflicts_by_obj)
