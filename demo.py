"""seqx 现状演示。

第一段：用朴素实现做一轮增删、翻转、区间加与区间统计，看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from seqx.seq import Seq, replay


def main():
    print("=== 朴素序列：按下标增删 ===")
    seq = Seq([1, 2, 3, 4, 5])
    print(f"  初始           -> {seq.to_list()}")
    seq.insert(2, 9)
    print(f"  insert(2, 9)   -> {seq.to_list()}")
    removed = seq.delete(0)
    print(f"  delete(0)      -> {removed}，序列 {seq.to_list()}")
    seq.set(1, 100)
    print(f"  set(1, 100)    -> {seq.to_list()}")

    print("=== 朴素序列：区间翻转与区间加 ===")
    seq.reverse(1, 4)
    print(f"  reverse(1, 4)  -> {seq.to_list()}")
    seq.add(0, 3, 10)
    print(f"  add(0, 3, 10)  -> {seq.to_list()}")

    print("=== 朴素序列：区间统计 ===")
    print(f"  sum(1, 4)      -> {seq.sum(1, 4)}")
    print(f"  min(1, 4)      -> {seq.min(1, 4)}")
    print(f"  max(1, 4)      -> {seq.max(1, 4)}")

    print("=== 朴素序列：操作序列回放 ===")
    final, results = replay(
        [5, 1, 4, 2, 3],
        [
            ("insert", 0, 0),
            ("reverse", 1, 4),
            ("add", 0, 5, 1),
            ("sum", 0, 5),
            ("min", 0, 5),
            ("max", 0, 5),
        ],
    )
    print(f"  末态           -> {final}")
    print(f"  逐步返回值     -> {results}")

    # TODO: 第二段演示（实现后补）
    # 说明：平衡树序列改造完成后，在这里补一段演示——用同一批固定下标与
    # 区间，在平衡树路径上做增删、区间翻转、区间加、区间求和与最值，逐步
    # 断言它与上面这条朴素路径给出的结果完全一致，并展示按下标查询单点值
    # 与中序还原出的整条序列，让新路径能直接跑通并正常退出。


if __name__ == "__main__":
    main()
