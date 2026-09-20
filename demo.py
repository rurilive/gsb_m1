"""ChangeLog 演示：单线变更与多分支合并。"""

from changelogd.changelog import ChangeLog
from changelogd.merge import DELETE, fork, merge, prefer_branch


def _clock(values):
    ticks = iter(values)
    return lambda: next(ticks)


def main():
    log = ChangeLog(clock=lambda: 0.0)

    print("=== 单线变更 ===")
    log.append("doc-1", "title", "草稿", 1)
    log.append("doc-1", "status", "draft", 1)
    log.append("doc-1", "title", "定稿", 3)
    log.append("doc-1", "tag", "release", 4)
    log.append("doc-1", "note", "旁注", 4)

    print("  变更全文：")
    for c in log.history("doc-1"):
        print(f"    v{c.version} {c.field} = {c.value!r}")

    for v in (1, 3, 4):
        print(f"  at('doc-1', {v}) -> {log.at('doc-1', v)}")

    print("\n=== 多分支合并：老张与小李从 v4 分叉 ===")
    zhang = fork(log, "zhang", clock=_clock([10.0, 15.0, 16.0]))
    zhang.log.append("doc-1", "title", "老张改的标题", 5)
    zhang.log.append("doc-1", "status", "done", 5)
    zhang.log.append("doc-1", "note", "老张还在改 note", 6)  # 老张又改了

    li = fork(log, "li", clock=_clock([11.0, 25.0, 26.0]))
    li.log.append("doc-1", "status", "review", 5)
    li.log.append("doc-1", "tag", "li-release", 5)
    li.log.append("doc-1", "note", DELETE, 5)  # 小李删了 note

    result = merge(
        "doc-1", log, [zhang, li], base_version=4,
        clock=_clock([100.0, 101.0, 102.0, 103.0, 104.0]),
    )

    print("  合并后全文（带来源）：")
    for m in result.history("doc-1"):
        where = ",".join(m.sources) if m.sources else "base"
        print(f"    v{m.version} {m.field} = {m.value!r:<20} <- {where}")

    print(f"  最终快照：{result.at('doc-1')}")

    print("  冲突账目：")
    for conflict in result.conflicts("doc-1"):
        losers = ", ".join(
            f"{c.change.value!r}({c.branch.name})" for c in conflict.losers
        )
        print(
            f"    {conflict.field}: 赢家 "
            f"{conflict.winner.change.value!r}({conflict.winner.branch.name})，"
            f"输家 {losers}"
        )

    print("\n=== 换个口径：同一次合并偏用小李的消解 ===")
    result_li = merge(
        "doc-1", log, [zhang, li], base_version=4,
        resolver=prefer_branch("li"),
        clock=_clock([200.0, 201.0, 202.0, 203.0, 204.0]),
    )
    print(f"  status 现在取：{result_li.at('doc-1')['status']!r}")
    loser = result_li.losers("doc-1")[0]
    print(f"  被消解的输家：{loser.field} = {loser.value!r}（原记录 ts={loser.ts}）")


if __name__ == "__main__":
    main()
