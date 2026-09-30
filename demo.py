"""nimgar 现状演示。

第一段：取一小批局面，看朴素递归给出的单堆赢输与最少取胜步数、多堆异或判胜负
与一条制胜走法、单个子游戏的格林数、多个独立子游戏之和的赢输，以及威索夫与
斐波那契两类取法的胜负与一条制胜走法。
第二段：预留的升级演示位子（见文末注释）。
"""

from nimgar import NimGar


def take_one_two(state):
    """每次取一至两颗的走法函数，供格林数与子游戏之和使用。"""
    return [s for s in (state - 1, state - 2) if s >= 0]


def main():
    print("=== 取石子游戏（现有朴素递归能力） ===")
    g = NimGar()

    print("--- 单堆取石子 ---")
    for n, cap in ((0, 3), (1, 3), (5, 3), (7, 3), (4, 3)):
        win = g.single_win(n, max_take=cap)
        least = g.single_min_takes(n, max_take=cap)
        print(f"  石子数 {n} 每次最多取 {cap} 颗：必胜 = {win}，最少取胜步数 = {least}")

    print("--- 多堆取石子（按位异或） ---")
    for heaps in ([], [0, 0, 0], [2, 2], [3, 4, 5], [1, 2, 3, 4, 5, 6, 7, 8]):
        print(
            f"  各堆 {heaps}：异或 = {g.multi_xor(heaps)}，"
            f"一条制胜走法 = {g.multi_winning_move(heaps)}"
        )

    print("--- 格林数与子游戏之和 ---")
    for n in range(6):
        print(f"  每次取一至两颗，石子数 {n} 的格林数 = {g.grundy(n, take_one_two)}")
    print(f"  两个石子数都为 1 的子游戏之和，先手必胜 = "
          f"{g.sum_win([1, 1], [take_one_two, take_one_two])}")
    print(f"  石子数分别为 2 与 3 的子游戏之和，先手必胜 = "
          f"{g.sum_win([2, 3], [take_one_two, take_one_two])}")

    print("--- 威索夫博弈 ---")
    for a, b in ((0, 0), (1, 2), (3, 5), (3, 3), (2, 3)):
        print(
            f"  两堆 {a} 与 {b}：先手必胜 = {g.wythoff_win(a, b)}，"
            f"一条制胜走法 = {g.wythoff_move(a, b)}"
        )

    print("--- 斐波那契博弈 ---")
    for n in (1, 2, 3, 4, 5, 6, 8, 10):
        print(
            f"  石子数 {n}：先手必胜 = {g.fib_win(n)}，"
            f"一条制胜走法 = {g.fib_move(n)}"
        )

    # TODO: 第二段演示（实现后补）
    # 升级实现到位后，在这里补一段演示：为每条能力另给一条独立做法（动态规划或
    # 记忆化递归），把单堆的模数口径、多堆的异或与制胜走法、格林数的整数序列、
    # 威索夫与斐波那契的固定口径结论并排打印，并把朴素递归展开次数与记忆化或
    # 异或路径的访问次数并排打印，让人看出两点差距。


if __name__ == "__main__":
    main()
