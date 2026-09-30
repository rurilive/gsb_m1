"""ivsched 现状演示。

第一段：登记若干闭区间，用穷举全部子集的口径求最大不相交区间数、带权最大权值
不相交集与具体选中的区间下标，并看几个规模计数。
第二段：预留的迭代演示位子（见文末注释）。
"""

from ivsched.core import NaiveIntervalScheduler


def main():
    print("=== 区间调度（现有朴素能力） ===")
    s = NaiveIntervalScheduler()
    s.add(0, 5, 2)
    s.add(3, 8, 3)
    s.add(10, 12, 4)
    s.add(11, 15, 1)
    print("  已登记区间:", s.intervals())
    print("  0 与 1 是否重叠:", s.overlaps(0, 1))
    print("  最大不相交区间数:", s.max_disjoint_count())
    print("  最大不相交的一批:", s.best_disjoint_selection())
    print("  带权最大权值:", s.max_weighted_value())
    print("  带权最大权值的一批:", s.best_weighted_selection())
    print("  全部不重叠子集:", s.all_disjoint_selections())
    print("  累计枚举子集数:", s.count_subsets())
    print("  累计重叠判定次数:", s.count_overlap_checks())
    print("  累计求和次数:", s.count_weight_sums())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
