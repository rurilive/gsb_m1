"""hanoi 现状演示。

第一段：朴素实现——递归生成完整的移动序列，在序列上数步数、取第 k 步、
逐步重放校验合法性，再演示四柱递推与限定规则变体。
第二段：预留的位运算直接定位与对拍演示位子（见文末注释）。
"""

from hanoi import (
    generate_moves,
    hanoi4,
    is_valid_sequence,
    kth_move,
    min_moves_restricted,
    min_moves_to,
    move_count,
    step_moves,
)


def main():
    print("=== 朴素递归生成完整序列 ===")
    n = 3
    print(f"  {n} 层最少步数 -> {move_count(n)}")
    print(f"  {n} 层完整移动序列（盘号, 起始柱, 目标柱）：")
    for index, step in enumerate(generate_moves(n)):
        print(f"    第 {index} 步 {step}")
    print(f"  把 {n} 层搬到中间柱的最少步数 -> {min_moves_to(n, 1)}")
    print(f"  第 2 步的移动 -> {kth_move(n, 2)}")

    good = step_moves(n)
    bad = list(good)
    bad[1], bad[2] = bad[2], bad[1]
    print(f"  递归生成的序列是否合法 -> {is_valid_sequence(n, good)}")
    print(f"  调换两步后的序列是否合法 -> {is_valid_sequence(n, bad)}")

    print("=== 四柱与限定规则变体 ===")
    for m in range(0, 5):
        print(f"  四柱 {m} 层最少步数 -> {hanoi4(m)}")
    for m in range(0, 4):
        print(f"  限定规则 {m} 层最少步数 -> {min_moves_restricted(m)}")

    # TODO: 第二段演示（实现后补）
    # 以位规律与位运算为核心：一条路径用分治递归求步数与生成序列，一条路径用
    # 二进制位直接定位第 k 步与某步的柱子，一条路径用位运算直接判定给定序列是否
    # 合法；三路互不调用，对同一批 n 逐项一致，并与小规模上枚举全部合法路径求
    # 最短路的结果逐项一致。再补四柱与限定规则变体的独立口径对照。实现后在这里
    # 加一段演示：打印三路结果、与小规模枚举的对拍结论、以及朴素生成长度对照。


if __name__ == "__main__":
    main()
