"""ChangeLog 演示：单线变更/快照重建，以及分叉合并。"""

from changelogd.changelog import ChangeLog
from changelogd.merge import DELETE, first_wins, merge


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
    # 分叉点：doc-1 在 v2 有标题、状态、截止日三个字段
    trunk = ChangeLog(clock=lambda: 0.0)
    trunk.append("doc-1", "title", "草稿", 1)
    trunk.append("doc-1", "status", "draft", 1)
    trunk.append("doc-1", "due", "2026-09-30", 2)

    # 老张从 v2 分叉：改标题、改状态、删截止日
    zhang = ChangeLog(clock=iter([10.0, 11.0, 12.0]).__next__)
    zhang.append("doc-1", "title", "老张定稿", 3)
    zhang.append("doc-1", "status", "shipped", 3)
    zhang.append("doc-1", "due", DELETE, 3)
    # 小李同版本分叉：改状态（撞车）、补标签、又动了已删的截止日
    li = ChangeLog(clock=iter([20.0, 21.0, 22.0]).__next__)
    li.append("doc-1", "status", "review", 3)
    li.append("doc-1", "tag", "hotfix", 3)
    li.append("doc-1", "due", "2026-10-01", 3)

    result = merge(
        "doc-1", 2,
        [("zhang", zhang), ("li", li)],
        base=trunk,
        clock=iter([100.0, 101.0, 102.0, 103.0]).__next__,
    )

    print("  合并记录（v4，逐条带来源）：")
    for entry in result.entries():
        shown = "<删除>" if entry.value is DELETE else repr(entry.value)
        print(f"    {entry.field} = {shown}  来源:{','.join(entry.sources)}")

    print("  冲突账与输家：")
    for conflict in result.conflicts():
        losers = "; ".join(
            f"{candidate.branch}={candidate.value!r}"
            for candidate in conflict.losers
        )
        print(f"    {conflict.field}: 赢家 {conflict.winner}，"
              f"输家 [{losers}]")

    print(f"  最终快照：{result.snapshot()}")

    print("\n=== 换个口径再合一次 ===")
    # 业务口径：status 冲突一律取 review；其余字段维持默认约定
    def status_review_wins(candidates, base_value):
        if candidates[0].change.field == "status":
            for candidate in candidates:
                if candidate.value == "review":
                    return candidate
        return first_wins(candidates, base_value)

    other = merge(
        "doc-1", 2,
        [("zhang", zhang), ("li", li)],
        base=trunk,
        clock=iter([200.0, 201.0, 202.0, 203.0]).__next__,
        resolver=status_review_wins,
    )
    print(f"  status 来源 {other.source_of('status')}，"
          f"due 来源 {other.source_of('due')}（已删除）")
    print(f"  最终快照：{other.snapshot()}")


if __name__ == "__main__":
    main()
