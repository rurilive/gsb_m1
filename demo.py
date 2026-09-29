"""mergekit 现状演示。

第一段：用 diff 逐位比较两段序列，看差异落在哪些下标；再用 merge 在只有
一侧改动时把改动抄过去。
第二段：预留的三方逐块合并、冲突标记与策略注入演示位子（见文末注释）。
"""

from mergekit import changes_only, diff, has_changes, merge


def show_diff(left, right):
    print("  左侧:", left)
    print("  右侧:", right)
    changes = changes_only(diff(left, right))
    if not changes:
        print("  两侧一致，无差异")
        return
    for change in changes:
        print("    下标 %d: %s 左=%r 右=%r" % (change.index, change.kind, change.left, change.right))


def main():
    print("=== 双向比较 ===")
    show_diff([1, 2, 3], [1, 2, 3])
    show_diff([1, 2, 3], [1, 2, 3, 4])
    show_diff([1, 2, 3, 4], [1, 2, 3])

    print()
    print("=== 三方合并（仅单侧改动） ===")
    base = ["a", "b", "c"]
    ours = ["a", "b", "c", "d"]
    theirs = ["a", "b", "c"]
    print("  基线:", base)
    print("  我方:", ours)
    print("  对方:", theirs)
    print("  合并:", merge(base, ours, theirs))
    print("  两侧都改过时:", end=" ")
    try:
        merge(base, ["x", "b", "c"], ["a", "b", "z"])
        print("未报冲突（不符合预期）")
    except Exception as exc:  # 现状只能报冲突，编辑脚本补齐后这里会变成逐块合并
        print(type(exc).__name__, "-", exc)

    # TODO(三方合并扩展): 编辑脚本、逐块三方合并与冲突策略补齐后，在这里加一段含冲突的演示：
    # 造一个三方都有改动的输入，让两侧在同一块各改各的，观察合并器把冲突块的整体范围
    # 与两侧各自内容都保留下来；再换一个 ours 或手动回调的策略重跑同一输入，比较输出差异。


if __name__ == "__main__":
    main()
