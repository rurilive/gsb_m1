"""catalanx 现状演示。

第一段：在一小组规模上看朴素实现给出的卡特兰数、栈模拟合法性判定、合法前缀计数、
全枚举过滤出来的合法序列，以及字典序取第几个与名次。
第二段：预留的升级演示位子（见文末注释）。
"""

from catalanx import Catalanx


def main():
    print("=== 卡特兰数与合法括号序列（现有朴素能力） ===")
    c = Catalanx()
    print(f"  第 4 个卡特兰数（递归展开） = {c.catalan_recursive(4)}")
    print(f"  递归展开次数 = {c.recursion_steps}")
    print(f"  递归访问次数 = {c.recurrence_visits}")
    print(f"  (()) 是否合法 = {c.is_valid('(())')}")
    print(f"  ())( 是否合法 = {c.is_valid('())(')}")
    print(f"  (()) 的合法前缀计数 = {c.valid_prefix_count('(())')}")
    seqs = c.enumerate_all(3)
    print(f"  长度 6 的合法序列 = {seqs}")
    print(f"  全枚举条数 = {c.full_enumeration_count}")
    print(f"  不越界单调路径条数 n=3 = {c.count_monotone_paths(3)}")
    print(f"  第 2 个合法序列（字典序从零起算） = {c.list_sequence(3, 2)}")
    print(f"  (())() 的字典序名次 = {c.rank_sequence('(())()')}")

    # TODO: 第二段演示（实现后补）
    # 记忆化与自底向上递推、组合公式与乘法逆元、按合法前缀剪枝的生成，以及按
    # 字典序取第 k 个与名次的互逆实现落地之后，在这里补一段演示：把递归路与递推路、
    # 递推路与组合公式路的卡特兰数逐项并排打印，把全枚举过滤与剪枝生成拿到的合法
    # 序列、按字典序取第几个与名次并排打印，把不越界单调路径计数与括号序列计数
    # 并排打印，并把递归展开次数、递推访问次数、全枚举条数与剪枝生成条数的规模
    # 差距一并打印出来。


if __name__ == "__main__":
    main()
