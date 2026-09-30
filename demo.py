"""sqrtds 现状演示。

第一段：用一个固定序列跑一遍现状的朴素操作，看区间加、区间求和、区间
最大值、区间计数与单点读改，以及回放一串操作后的末态与元素访问计数；
第二段：预留的分块与独立做法演示位子（见文末注释）。
"""

from sqrtds.seq import Sequence


def main():
    print("=== 朴素逐元素处理 ===")
    data = [3, -1, 4, 1, 5, -9, 2, 6]
    s = Sequence(data)
    print("  序列 %s，长度 %d" % (data, s.size()))

    print("  区间 [0, 8) 求和 %d" % s.sum_range(0, 8))
    print("  区间 [2, 5) 求和 %d" % s.sum_range(2, 5))
    print("  区间 [0, 8) 最大值 %d" % s.max_range(0, 8))
    print("  区间 [0, 8) 内等于 1 的个数 %d" % s.count_range(0, 8, 1))

    s.add_range(0, 4, 1)
    print("  区间 [0, 4) 每个位置加 1 后 %s" % s.data)

    s.set(3, 100)
    print("  单点 set(3, 100) 后 get(3) 得到 %d" % s.get(3))

    ops = [
        ("sum", 0, 8),
        ("add", 0, 2, 1),
        ("max", 0, 4),
        ("count", 0, 8, 1),
        ("get", 3),
    ]
    final, results = Sequence.replay(data, ops)
    print("  回放 %d 步，逐返回值 %s" % (len(ops), results))
    print("  回放末态 %s" % final)
    print("  累计元素访问计数 %d" % s.element_touches)

    # TODO: 第二段演示（实现后补）
    # 分块与独立做法实现后，在这里加一段演示：拿一批区间加、区间求和、
    # 区间最大值、区间计数与单点查询，用分块路径一次性回答并打印每个查询
    # 的结果，打印块数与被访问元素计数，再把分块路径与朴素逐元素路径的
    # 累计访问量分列对照，确认差距明显。


if __name__ == "__main__":
    main()
