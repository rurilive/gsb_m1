"""satx 现状演示。

第一段：朴素枚举——把全部变量取值的组合逐一列出，找出满足全部约束的赋值。
第二段：预留的蕴含图强连通分量演示位子（见文末注释）。
"""

from satx import TwoSat


def baseline_demo():
    print("== 第一段：基线枚举能力 ==")
    sat = TwoSat(3).add_clause(-1, 2).add_clause(1, 1).add_clause(-2, 3)
    print("约束:", sat.clauses())
    print("变量个数:", sat.var_count(), " 暴力要查的赋值个数:", sat.enumeration_size())
    print("是否可满足:", sat.is_satisfiable())
    print("一组方案:", sat.solve())
    print("变量 3 的取值:", sat.value_of(3))
    print("满足的约束条数:", sat.satisfied_count(sat.solve()))
    print("满足全部约束的赋值个数:", sat.count_models())


def main():
    baseline_demo()
    print("== 第二段：蕴含图强连通分量与方案 ==")
    # TODO(蕴含图强连通分量): 把每个约束改写成两条蕴含边，在蕴含图上用一次
    # 深度优先搜索求强连通分量，某变量与其取反落在同一分量即不可满足；可满足
    # 时按分量拓扑序的反序给出一组赋值。实现后在这里加一段演示：用同一批约束
    # 跑强连通分量路径，打印蕴含图边数与暴力枚举规模的差距，并把可满足性、方案
    # 与满足的约束条数同基线逐项对一遍；再补上带权最优指派或字典序最小方案的
    # 演示。


if __name__ == "__main__":
    main()
