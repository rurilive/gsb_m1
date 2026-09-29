"""beatsx 现状演示。

第一段：造一个数组，跑一遍基线 NaiveSeg 的求和、取最值与区间取最值，看结果；
第二段：区间取最值与求和混合的演示位子（见文末注释）。
"""

from beatsx.seg import NaiveSeg


def main():
    print("=== 基线 NaiveSeg 逐项处理 ===")
    data = [3, 1, 4, 1, 5, 9, 2, 6]
    seg = NaiveSeg(data)
    print("  初始数组 %s，元素个数 %d" % (seg.to_list(), seg.n))
    print("  整段求和 %d" % seg.range_sum(0, seg.n))
    print("  子区间 [2, 5) 求和 %d" % seg.range_sum(2, 5))
    print("  整段最大 %d，整段最小 %d" % (seg.range_max(0, seg.n), seg.range_min(0, seg.n)))

    seg.chmin(1, 6, 4)
    print("  对 [1, 6) 取较小值 4 之后 %s" % seg.to_list())
    seg.chmax(0, 3, 3)
    print("  再对 [0, 3) 取较大值 3 之后 %s" % seg.to_list())
    print("  空区间 [3, 3) 求和 %d" % seg.range_sum(3, 3))

    # TODO: 第二段演示（实现后补）
    # 目标结构补出来之后，在这里加一段：用同一个数组跑一串「区间加、区间取最值、
    # 区间求和」的混合操作，打印每一步的求和结果与下推计数，展示剪枝后访问节点数
    # 明显小于逐项扫描次数，再与基线 NaiveSeg 对同一批操作的结果逐项核对。


if __name__ == "__main__":
    main()
