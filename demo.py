"""mqdp 现状演示。

第一段：用朴素实现跑一遍窗口约束动态规划，逐前驱枚举求前缀值表。
第二段：预留的双端队列优化演示位子（见文末注释）。
"""

from mqdp.tables import MAX_POLICY, MIN_POLICY, WindowDP


def main():
    values = [3, 1, 4, 1, 5, 9, 2, 6]
    window = 3

    planner = WindowDP(window, 1, MIN_POLICY)
    print("=== 朴素窗口约束动态规划（现有能力）===")
    print("  序列       ->", values)
    print("  窗口长度   ->", window)
    print("  转移系数   ->", planner.coef)
    print("  转移口径   ->", planner.policy)
    print("  前缀值表   ->", planner.forward(values))
    print("  末尾答案   ->", planner.answer(values))
    print("  取小前驱   ->", planner.steps(values))

    print("=== 两条口径 === ")
    print("  取最小     ->", WindowDP(window, 1, MIN_POLICY).forward(values))
    print("  取最大     ->", WindowDP(window, 1, MAX_POLICY).forward(values))

    print("=== 独立窗口枚举与逐前驱一致 === ")
    print("  独立枚举表 ->", planner.window_scan(values))
    print("  逐项一致   ->", planner.matches(values))

    print("=== 边界一路看 ===")
    print("  窗口为一   ->", WindowDP(1, 1).forward([2, 5, 1, 4, 3]))
    print("  窗口等于长度 ->", WindowDP(len(values), 1).forward(values))
    print("  窗口大于长度 ->", WindowDP(99, 1).forward(values))
    print("  空序列     ->", WindowDP(2, 1).answer([]))

    print("=== 朴素对比次数 ===")
    print("  规模为8的枚举次数 ->", planner.compare_count(8))
    print("  规模为二千的枚举次数 ->", planner.compare_count(2000))

    # TODO: 第二段演示（实现后补）
    # 说明：单调双端队列就位后，在这里补一段演示——用队首出窗口、队尾按
    # 单调性弹出劣解的走法维护滑动窗口内的最优前缀值，把取窗口最优的一类
    # 转移从平方降到线性，再用另起一条独立做法在固定输入上逐项对照，看
    # 平方级别的枚举次数换成了单趟线性扫描后的提速。


if __name__ == "__main__":
    main()
