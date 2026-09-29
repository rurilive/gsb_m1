"""sketchly 现状演示。

第一段：用朴素精确计数记几笔，看去重键数、单键次数与合计。
第二段：预留的计数草图、误差界与合并演示位子（见文末注释）。
"""

from sketchly import ExactCounter


def main():
    print("=== 朴素精确计数（现有能力） ===")
    exact = ExactCounter()
    for word in ["alpha", "beta", "alpha", "gamma", "alpha", "beta"]:
        exact.add(word)
    print("  记过的键 ->", sorted(exact.keys()))
    print("  alpha 次数 ->", exact.value("alpha"))
    print("  beta 次数  ->", exact.value("beta"))
    print("  gamma 次数 ->", exact.value("gamma"))
    print("  没记过的键 ->", exact.value("delta"))
    print("  合计 ->", exact.total())

    other = ExactCounter()
    other.add_many(["alpha", "delta", "delta"])
    exact.merge(other)
    print("  合并另一批之后 alpha ->", exact.value("alpha"))
    print("  合并之后 delta ->", exact.value("delta"))
    exact.reset()
    print("  reset 之后合计 ->", exact.total())

    # TODO(计数草图改造): 计数器草图就位后在这里补一段演示：
    # 构造一个指定行数与每行宽度的草图，对同一批键逐个插入，打印若干
    # 键的估计值与精确值对照，说明估计只高不低；再拿两个同参数草图按
    # 对应计数器相加合并，打印合并后的估计，确认与把两批数据一起建草
    # 图一致；再演示一次把已插入的键减回以及用前缀草图相减得到的区间
    # 估计。行数与宽度越大估计越接近真实这一点应在打印里直接看得见。


if __name__ == "__main__":
    main()
