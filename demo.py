"""ChangeLog 现状演示。

第一段：单条时间线上追加变更、取全文、重建旧版本快照。
第二段：从同一版本分叉两条分支，各自改动后三方合并。
"""

from changelogd.changelog import ChangeLog
from changelogd.merge import merge


def main():
    log = ChangeLog(clock=lambda: 0.0)

    print("=== 单线变更 ===")
    log.append("doc-1", "title", "草稿", 1)
    log.append("doc-1", "status", "draft", 1)
    log.append("doc-1", "title", "定稿", 3)
    log.append("doc-1", "tag", "release", 4)

    print("  变更全文：")
    for c in log.history("doc-1"):
        print(f"    v{c.version} {c.field} = {c.value!r}")

    for v in (1, 3, 4):
        print(f"  at('doc-1', {v}) -> {log.at('doc-1', v)}")

    print("\n=== 多分支合并 ===")
    ticks = iter(range(1, 100))
    clock = lambda: float(next(ticks))

    base = ChangeLog(clock=clock)
    base.append("doc-1", "title", "草稿", 1)
    base.append("doc-1", "status", "draft", 1)
    base.append("doc-1", "note", "临时备注", 1)

    zhang = ChangeLog(clock=clock)  # 老张：改标题、状态，删掉备注
    zhang.append("doc-1", "title", "定稿", 2)
    zhang.append("doc-1", "status", "review", 2)
    zhang.delete("doc-1", "note", 2)

    li = ChangeLog(clock=clock)  # 小李：也动状态，补标签，改了备注
    li.append("doc-1", "status", "published", 3)
    li.append("doc-1", "tag", "release", 3)
    li.append("doc-1", "note", "小李改的备注", 3)

    result = merge(base.history("doc-1"), zhang.history("doc-1"), li.history("doc-1"))

    print("  合并结果（含来源）：")
    for mc in result.changes:
        c = mc.change
        print(f"    [{mc.origin:>8}] v{c.version} {c.field} = {c.value!r}")

    print("  冲突台账（被消解的输家）：")
    for conflict in result.conflicts:
        losers = [(l.origin, l.change.value) for l in conflict.losers]
        print(
            f"    {conflict.field}: 采用 [{conflict.winner.origin}] "
            f"{conflict.winner.change.value!r}，消解 {losers}"
        )

    merged = result.apply_to(ChangeLog(clock=clock))
    print(f"  最终快照：{merged.at('doc-1', 99)}")


if __name__ == "__main__":
    main()
