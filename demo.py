"""hullx 快速演示。

第一段跑改造前的基线能力（朴素凸包、直径、最小外接矩形、宽度）。
第二段预留给改造后的高效路径演示（排序凸包与旋转卡壳），待实现补齐。
"""

from hullx.hull import HullKit


def demo_baseline():
    print("== 基线：朴素凸包路径 ==")
    k = HullKit()

    pts = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0),
           (2.0, 2.0), (1.0, 1.0)]
    hull = k.convex_hull(pts)
    print("凸包顶点 =", hull)
    print("枚举点对数 =", k.hull_pairs, " 侧判定次数 =", k.hull_side_checks)

    d, pair = k.diameter(pts)
    print("直径 =", d, " 点对 =", pair, " 配对次数 =", k.diameter_pairs)

    rect = k.min_bounding_rect(pts)
    print("最小外接矩形 面积 =", rect["area"],
          " 宽 =", rect["width"], " 高 =", rect["height"])
    print("朝向枚举对数 =", k.rect_pairs,
          " 投影点数 =", k.rect_point_checks)

    print("宽度 =", k.width(pts))

    collinear = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
    print("全共线凸包 =", k.convex_hull(collinear))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
