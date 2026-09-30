"""votehal 现状演示。

第一段：用反复重扫的朴素做法求频次、多数元素、前几频繁元素与
超过元素种类数分之一的众数，并打印对序列的完整重扫次数；
第二段：预留的摩尔投票、哈希计数与推广投票演示位子（见文末注释）。
"""

from votehal.naive import (
    VoteTools,
    frequent_values,
    has_majority,
    majority_count,
    majority_value,
    naive_counts,
    top_frequent,
    two_pass_majority,
)


def main():
    print("=== 朴素反复重扫 ===")
    seq = [1, 1, 2, 3, 3, 3]
    print("  序列 %s" % seq)
    print("  各元素次数 %s" % (naive_counts(seq),))

    tools = VoteTools(seq)
    tools.reset_rescan_count()
    tools.counts()
    print("  完整重扫次数 %d" % tools.rescan_count())
    print("  逐元素比较次数 %d" % tools.visit_count())

    print("  多数元素 %s 次数 %d"
          % (majority_value(seq), majority_count(seq)))
    print("  是否存在多数元素 %s" % has_majority(seq))
    print("  超过三分之一 %s" % (frequent_values(seq, 3),))
    print("  前二频繁 %s" % (top_frequent(seq, 2),))

    print()

    # TODO: 第二段演示（实现后补）
    #
    # 在 votehal 里补出摩尔投票法、哈希计数与推广投票法之后，在这里加一
    # 段演示：对同一批数据，投票路一趟求出候选再做验证、哈希计数路一趟
    # 统计频次再筛选，两条路给出的多数元素值、出现次数、前几频繁元素与
    # 是否存在多数元素逐项一致；再用保留至多 k 减一个候选的推广投票法一
    # 趟求出超过元素种类数分之一的元素，与朴素筛选对照；打印朴素重扫次
    # 数与投票、哈希访问次数的规模差距；最后覆盖空序列、单元素、无多数、
    # 恰好一半、全相同、全不同、多数在两端、含负值与重复、k 等于一、k
    # 大于元素种类数这些边界，确认各条路径结论一致。

    print("=== 两遍哈希做法 ===")
    value, hit, visited = two_pass_majority(seq)
    print("  多数元素 %s 次数 %d" % (value, hit))
    print("  逐元素访问次数 %d" % visited)


if __name__ == "__main__":
    main()
