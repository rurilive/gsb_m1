"""joseph 现状演示。

第一段：在一小组参数上看朴素模拟给出的淘汰序列、最后幸存者、第几个被淘汰、
淘汰的次序编号，以及从头开始的编号口径与搬家步数的规模增长。
第二段：预留的升级演示位子（见文末注释）。
"""

from joseph import Josephus


def main():
    print("=== 约瑟夫环淘汰过程（现有朴素模拟能力） ===")
    sim = Josephus(5, 2)
    print(f"  人数 5 步长 2 的淘汰序列 = {sim.order()}")
    print(f"  最后幸存者 = {Josephus(5, 2).survivor()}")
    print(f"  第 3 个被淘汰者 = {Josephus(5, 2).rank_to_be_removed(3)}")
    print(f"  编号 3 是第几个被淘汰 = {Josephus(5, 2).elimination_index(3)}")
    print(f"  步长为 1 时顺序淘汰 = {Josephus(4, 1).order()}")
    print(f"  步长大于人数时回绕 = {Josephus(3, 7).order()}")

    print("--- 从头开始编号的口径 ---")
    print(f"  人数 5 步长 2 从一开始编号 = {Josephus(5, 2, convention='one').order()}")
    print(f"  人数 0 时没有幸存者（抛异常）")

    print("--- 朴素路径的搬家代价 ---")
    for n in (10, 20, 40):
        print(f"  人数 {n} 步长 2 的搬家总步数 = {Josephus(n, 2).move_count()}")
    print(f"  人数 6 步长 2 每次淘汰后的累计搬家 = {Josephus(6, 2).move_counts_per_step()}")

    # TODO: 第二段演示（实现后补）
    # 数学递推求幸存者、平衡结构跳跃求整条序列、分块跳跃一次性削减这三路实现后，
    # 在这里并排打印三路与朴素在同一批参数上的淘汰序列与幸存者，把变体口径的各路
    # 结果一并打印，并把递推步数、跳跃削减次数与朴素搬家步数的规模差距打出来。


if __name__ == "__main__":
    main()
