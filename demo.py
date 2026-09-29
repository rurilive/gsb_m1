"""geox 快速演示。

第一段跑改造前的基线能力（凸包、最近点对、线段相交、点在多边形内）。
第二段预留给改造后的高效路径演示（旋转卡壳直径等），待实现补齐。
"""

from geox.geom import PlanarGeom


def demo_baseline():
    print("== 基线：朴素几何路径 ==")
    g = PlanarGeom()

    pts = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0),
           (2.0, 2.0), (1.0, 1.0)]
    hull = g.convex_hull(pts)
    print("凸包顶点 =", hull, " 比较次数 =", g.hull_comparisons)

    d, pair = g.closest_pair(pts)
    print("最近点对距离 =", d, " 点对 =", pair,
          " 比较次数 =", g.closest_comparisons)

    print("线段相交（交叉）=", g.segments_intersect(
        (0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)))
    print("线段相交（共线重叠）=", g.segments_intersect(
        (0.0, 0.0), (3.0, 0.0), (1.0, 0.0), (5.0, 0.0)))

    square = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]
    print("点在多边形内（内部）=", g.point_in_polygon((2.0, 2.0), square))
    print("点在多边形内（边上）=", g.point_in_polygon((2.0, 0.0), square))
    print("点在多边形内（外部）=", g.point_in_polygon((5.0, 2.0), square))


def demo_optimized():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    demo_baseline()
    demo_optimized()


if __name__ == "__main__":
    main()
