"""calipers 快速演示。

第一段跑改造前的基线能力（朴素凸包、最近点对、直径、宽度、最大三角形、
外接圆、包含判定、最小面积外接矩形）。
第二段预留给改造后的高效路径演示（旋转卡壳与分治最近点对），待实现补齐。
"""

from calipers.calipers import CalipersKit


def demo_baseline():
    print("== 基线：朴素几何度量路径 ==")
    k = CalipersKit()

    pts = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0),
           (2.0, 2.0), (1.0, 1.0), (3.0, 1.0)]
    hull = k.convex_hull(pts)
    print("凸包顶点 =", hull)
    print("凸包枚举点对数 =", k.hull_pairs, " 侧判定次数 =", k.hull_checks)

    d2, pair = k.closest_pair(pts)
    print("最近点对距离平方 =", d2, " 点对 =", pair,
          " 枚举点对数 =", k.closest_pairs)

    dd2, dpair = k.hull_diameter(pts)
    print("直径距离平方 =", dd2, " 点对 =", dpair,
          " 配对次数 =", k.diameter_pairs)

    print("最小宽度 =", k.min_width(pts))

    area, tri = k.max_triangle(pts)
    print("最大三角形面积 =", area, " 顶点 =", tri,
          " 枚举三元组数 =", k.triangle_ops)

    circ = k.circumcircle(pts)
    print("外接圆圆心 =", circ["center"], " 半径 =", circ["radius"],
          " 枚举点对 =", k.circle_pairs, " 三元组 =", k.circle_triples)

    print("含内部点 =", k.contains(pts, (2.0, 2.0)),
          " 含边界点 =", k.contains(pts, (4.0, 0.0)),
          " 含外部点 =", k.contains(pts, (9.0, 9.0)))

    rect = k.min_area_rect(pts)
    print("最小面积外接矩形 面积 =", rect["area"],
          " 角点 =", rect["corners"], " 朝向枚举数 =", k.rect_edges)

    collinear = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
    print("全共线凸包 =", k.convex_hull(collinear),
          " 宽度 =", k.min_width(collinear))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
