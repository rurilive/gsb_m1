"""deltafy 现状演示。

第一段：用朴素逐行比较器比较两段行数相同、内容有差异的文本，
看到它按位置记下替换。
第二段：预留的差分、补丁与三方合并演示位子（见文末注释）。
"""

from deltafy.compare import LineDiff


def main():
    print("=== 朴素逐行比较 ===")
    old = "alpha\nbeta\ngamma\ndelta"
    new = "alpha\nBETA\ngamma\nDELTA"
    diff = LineDiff(old, new)
    for op in diff.operations():
        print("  %s" % (op,))
    print("  替换行数 -> %d" % diff.changed_count())
    print("  相同行数 -> %d" % diff.same_count())

    # TODO(差分与补丁改造): 在 deltafy 里把逐行比较扩成完整差分引擎（基于最长
    # 公共子序列的最小编辑脚本、带上下文行且可裁剪边界的补丁、补丁应用与回滚、
    # 幂等与交换、以及非冲突自动合入的三方合并）之后，在这里补三段演示：先用
    # 两段含插入与删除的文本产出编辑脚本并打印增、删、相等三类操作；再把脚本
    # 序列化成补丁、应用到旧文本并与目标文本逐字符比对；最后给一份基础文本与
    # 两侧改动，打印合并结果、冲突区间与冲突数量，确认纯插入与纯删除没有误判。


if __name__ == "__main__":
    main()
