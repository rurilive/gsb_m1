"""ChangeLog 现状演示。

第一段：单条时间线上追加变更、取全文、重建旧版本快照。
第二段：预留的多分支合并演示位子（见文末注释）。
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

    # TODO(合并改造): 多分支合并实现后，在这里加一段演示：
    # 从某个版本分叉出两条分支，各自 append（含同字段不同值的冲突、
    # 各自独有的字段、以及删除后又被人改的字段），按默认策略合并，
    # 打印合并结果的来源标注与被消解掉的输家。

    print("\n=== 多分支合并（待实现） ===")
    print("  见上方 TODO 注释。")


if __name__ == "__main__":
    main()
