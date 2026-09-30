"""twosat 现状演示。

第一段: 直接跑朴素枚举, 在一批固定公式上打印可行赋值、可满足判定与解计数。
第二段: 预留的蕴含图求解演示位子 (见文末注释)。
"""

from twosat import count_solutions, is_satisfiable, solve, verify


def show(name, n, clauses):
    assign = solve(n, clauses)
    print("  %s -> assign=%s sat=%s count=%s"
          % (name, assign, is_satisfiable(n, clauses), count_solutions(n, clauses)))
    if assign is not None:
        print("       verify=%s" % (verify(n, clauses, assign),))


def main():
    print("=== 朴素二可满足性 (逐变量枚举) ===")
    show("无子句三个变量", 3, [])
    show("单子句", 2, [(1, 2)])
    show("恒真子句", 1, [(1, -1)])
    show("直接矛盾", 1, [(1, 1), (-1, -1)])
    show("三变量混合", 3, [(1, 2), (-2, 3), (-1, -3)])
    show("零变量", 0, [])

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
