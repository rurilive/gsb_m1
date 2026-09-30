"""chainkit 演示：第一段直跑朴素能力，第二段留待实现后补。"""

from chainkit import (
    naive_max_optimal,
    naive_triangle,
    plan_to_string,
    whole_count,
    whole_max_cost,
    whole_optimal,
)


def first_section():
    """第一段：直跑朴素实现，展示最少次数、方案、方案个数与派生问题。"""
    dims = [30, 35, 15, 5, 10, 20, 25]
    cost, plan = whole_optimal(dims)
    text = plan_to_string(dims, plan)
    print("链维度:", dims)
    print("最少乘法次数:", cost)
    print("最优加括号方案:", text)
    print("最少次数的方案个数:", whole_count(dims))

    max_cost, max_plan = naive_max_optimal(dims, 0, len(dims) - 2)
    print("最大乘法次数:", max_cost)
    print("最大次数的方案:", plan_to_string(dims, max_plan))

    print("整条链最大次数:", whole_max_cost(dims))
    print("多边形三角剖分最低代价:", naive_triangle([30, 35, 15, 5, 10, 20]))


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    first_section()
