"""halfplane 现状演示。

第一段：枚举求交与面积——用四条内向半平面围出单位正方形，打印顶点与面积。
第二段：预留的排序加双端队列做法与独立做法对照演示位子（见文末注释）。
"""

from halfplane import HalfPlane, intersect, polygon_area


def main():
    print("=== 枚举交点求单位正方形（基线） ===")
    hps = [
        HalfPlane((0, 0), (1, 0)),
        HalfPlane((1, 0), (1, 1)),
        HalfPlane((1, 1), (0, 1)),
        HalfPlane((0, 1), (0, 0)),
    ]
    res = intersect(hps)
    for p in res.vertices:
        print("  顶点 (%s, %s)" % (p[0], p[1]))
    print("  面积 %s" % res.area)
    print("  鞋带复核 %s" % polygon_area(res.vertices))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
