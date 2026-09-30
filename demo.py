"""rangeseg 现状演示。

第一段：用一个固定序列跑一遍现状的朴素区间操作，看区间求和、区间加、
区间赋值、区间最值与单点读改，以及回放一串操作后的末态与访问计数；
第二段：预留的线段树与懒标记演示位子（见文末注释）。
"""

from rangeseg.seq import RangeSeq


def main():
    print("=== 朴素整段重扫 ===")
    data = [3, -1, 4, 1, 5, -9, 2, 6]
    s = RangeSeq(data)
    print("  序列 %s，长度 %d" % (data, s.size()))

    print("  区间 [0, 8) 求和 %d" % s.sum(0, 8))
    print("  区间 [2, 5) 求和 %d" % s.sum(2, 5))
    print("  区间 [0, 8) 最小值 %d，最大值 %d" % (s.min_val(0, 8), s.max_val(0, 8)))

    s.add(0, 4, 1)
    print("  区间 [0, 4) 每个元素加 1 后 %s" % s.data)

    s.assign(5, 7, 0)
    print("  区间 [5, 7) 整体改写成 0 后 %s" % s.data)

    s.set(3, 100)
    print("  单点 set(3, 100) 后 get(3) 得到 %d" % s.get(3))

    ops = [
        ("sum", 0, 8),
        ("add", 0, 2, 1),
        ("min", 0, 4),
        ("max", 0, 4),
        ("get", 3),
    ]
    final, results = RangeSeq.replay(data, ops)
    print("  回放 %d 步，逐返回值 %s" % (len(ops), results))
    print("  回放末态 %s" % final)
    print("  至今逐项扫描累计访问 %d 次" % s.taken())

    # TODO: 第二段演示（实现后补）
    # 线段树与懒标记实现后，在这里加一段演示：拿一批区间加、区间求和、区间
    # 赋值与区间最值查询，用带懒标记的线段树一次性回答，打印每个查询的结果，
    # 并打印区间操作访问的结点数与懒标记下推次数，与朴素路径逐项重扫的访问量
    # 放在一起对照，确认树上的访问量明显更小；再演示可持久化版本与区间和差分
    # 口径的交叉核对，确认新老两条路径对同一批数据逐项一致。


if __name__ == "__main__":
    main()
