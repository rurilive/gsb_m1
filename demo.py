"""sparsetable 现状演示。

第一段：构造一个整数序列，逐个区间求最小值、最大值与最小值的下标。
第二段：预留的稀疏表演示位子（见文末注释）。
"""

from sparsetable.rmq import NaiveRMQ


def main():
    print("=== 朴素区间最值（现有能力） ===")
    q = NaiveRMQ([5, 2, 8, 1, 9, 3, 7])
    print("  序列             ->", q.as_list())
    print("  长度             ->", len(q))
    ranges = [(0, 7), (0, 1), (1, 4), (3, 3), (4, 7)]
    for l, r in ranges:
        print(
            "  [{}, {}) min/max/argmin -> {} / {} / {}".format(
                l, r, q.query_min(l, r), q.query_max(l, r), q.query_argmin(l, r)
            )
        )
    print("  批量最小值       ->", q.query_many(ranges))

    # TODO: 第二段演示（实现后补）
    # 稀疏表改造完成后，在这里补一轮演示：
    # 对同一序列用稀疏表求区间最小值与最大值，并对一个二维矩阵求子矩阵最大值；
    # 把稀疏表结果与上面的逐项扫描结果并排打印，展示两条路口径逐项一致。


if __name__ == "__main__":
    main()
