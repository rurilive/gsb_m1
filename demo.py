"""ChangeLog 现状演示。

第一段：单条时间线上追加变更、取全文、重建旧版本快照。
第二段：老张和小李从同一版本分叉，含冲突、独有字段、删除后又改，
按默认策略合并，并打印来源标注、最终快照与输家对账。
"""

from changelogd.changelog import ChangeLog


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
    from changelogd.changelog import DELETE

    base = ChangeLog(clock=lambda: 0.0)
    base.append("doc-2", "title", "需求稿", 1)
    base.append("doc-2", "status", "draft", 1)
    base.append("doc-2", "wip", "待确认", 1)

    zhang = base.fork(1, "zhang")
    zhang.append("doc-2", "title", "老张定稿", 2)
    zhang.append("doc-2", "status", "review", 2)
    zhang.append("doc-2", "wip", DELETE, 2)

    li = base.fork(1, "li")
    li.append("doc-2", "status", "done", 2)
    li.append("doc-2", "tag", "hot", 2)
    li.append("doc-2", "wip", "小李还在改", 2)

    merge_tick = iter(range(100, 110))
    report = base.merge_branches(
        1, [("zhang", zhang), ("li", li)], clock=lambda: next(merge_tick))

    print("  合并落线（输家先落，赢家后落）：")
    for entry in report.merged:
        mark = "赢" if entry.state == "winner" else "输"
        print(f"    v{entry.change.version} [{entry.branch}:{mark}] "
              f"{entry.change.field} = {entry.change.value!r}")

    print(f"  合并版本 {report.version} 的最终快照：{base.at('doc-2', report.version)}")
    print("  被消解的输家：")
    for entry in report.losers():
        print(f"    {entry.change.field} = {entry.change.value!r}"
              f"（来自 {entry.branch}）")
    print("  wip 的中间经过仍在历史里：")
    for change in base.history("doc-2"):
        if change.field == "wip":
            print(f"    v{change.version} wip = {change.value!r}")


if __name__ == "__main__":
    main()
