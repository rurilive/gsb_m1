"""waveletx 现状演示。

第一段：用朴素区间索引对固定数组跑四项查询，打印结果与每次查询的比较次数；
第二段：预留的小波树与持久化权值线段树的演示位子（见文末注释）。
"""

from waveletx.naive import NaiveRangeIndex, count_equal, count_leq
from waveletx.naive import kth_smallest, range_rank


def main():
    print("=== 朴素区间查询 ===")
    values = [5, 1, 4, 1, 9, 2, 6, 3]
    index = NaiveRangeIndex(values)
    print("  数组 %s" % (values,))
    print("  区间 [1, 7) 第零小 %d" % index.kth_smallest(1, 7, 0))
    print("  区间 [1, 7) 第二小 %d" % index.kth_smallest(1, 7, 2))
    print("  值 4 在 [0, 8) 的排名 %d" % index.range_rank(0, 8, 4))
    print("  区间 [2, 6) 不超过 4 的个数 %d" % index.count_leq(2, 6, 4))
    print("  区间 [0, 8) 中 1 出现次数 %d" % index.count_equal(0, 8, 1))
    print("  上述查询累计比较次数 %d" % index.comparison_count())

    index.reset_comparisons()
    print("  清零后再跑一遍单点区间 [3, 4) 第零小 %d"
          % index.kth_smallest(3, 4, 0))
    print("  单点查询比较次数 %d" % index.comparison_count())
    print("  模块级函数区间 [0, 4) 第零小 %d"
          % kth_smallest(values, 0, 4, 0))
    print("  模块级函数值 2 在 [0, 8) 的排名 %d"
          % range_rank(values, 0, 8, 2))

    # TODO: 第二段演示（实现后补）
    #
    # 在 waveletx 里补出小波树与持久化权值线段树之后，在这里加一段演示：
    # 对同一批区间查询，用两条新路径各跑一遍，再与上面朴素路径的结果逐项
    # 对照，确认区间第 k 小、排名、不超过某值的个数、某值出现次数四项完
    # 全一致；打印小波树每层访问次数与朴素比较次数，多次查询下展示两者的
    # 规模差距；覆盖空数组、单元素、区间端点贴数组两端、区间长度为一时的
    # 第零小、k 越界、值全相同、含负值、值域很大需压缩成秩、非法区间这些
    # 边界，确认新路径与朴素路径、以及两条新路径之间结论都一致。

    print("  区间 [0, 8) 不超过 9 的个数"
          " %d" % count_leq(values, 0, 8, 9))
    print("  区间 [1, 3) 中 1 出现次数 %d"
          % count_equal(values, 1, 3, 1))


if __name__ == "__main__":
    main()
