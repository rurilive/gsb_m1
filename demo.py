"""kdtree 现状演示。

第一段：在固定点集上演示范围查询与最近邻查询的朴素能力。
第二段：预留的 k 维树演示位子（见文末注释）。
"""

from kdtree.scan import nearest, points_in_box


def main():
    points = [
        (0, 0),
        (3, 4),
        (7, 1),
        (2, 9),
        (5, 5),
        (8, 8),
    ]
    print("=== 范围与最近邻（朴素扫描）===")
    print(f"  points_in_box 闭矩形 [(1,1),(6,6)] = {points_in_box(points, ((1, 1), (6, 6)))}")
    print(f"  points_in_box 空矩形 [(9,9),(10,10)] = {points_in_box(points, ((9, 9), (10, 10)))}")
    print(f"  nearest((0,0)) = {nearest(points, (0, 0))}")
    print(f"  nearest((6,6)) = {nearest(points, (6, 6))}")

    # TODO: 第二段演示（实现后补）
    # k 维树实现后，在这里加一段演示：交替按维度取中位数建树、
    # 范围查询按包围盒剪枝、最近邻按当前最优与分割面距离剪枝，
    # 并与朴素扫描逐项对照。


if __name__ == "__main__":
    main()
