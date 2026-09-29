"""geolib 现状演示。

第一段：造一个 FlatIndex，插入若干矩形，跑点包含、矩形相交、最近邻，看现状结果；
第二段：预留空间划分树演示位子（见文末注释）。
"""

from geolib.spatial import FlatIndex


def main():
    print("=== 线性扫描现状 ===")
    idx = FlatIndex()
    idx.insert((0.0, 0.0, 1.0, 1.0), "a")
    idx.insert((2.0, 2.0, 4.0, 4.0), "b")
    idx.insert((0.5, 0.5, 3.0, 3.0), "c")
    print("  矩形数 %d，标识 %s" % (idx.count(), idx.names()))
    print("  点 (0.75, 0.75) 命中 %s" % (idx.contains_point(0.75, 0.75),))
    print("  矩形 (2.5, 2.5, 3.5, 3.5) 相交 %s" % (
        idx.intersect((2.5, 2.5, 3.5, 3.5)),
    ))
    print("  点 (-1, -1) 最近标识 %s" % (idx.nearest(-1.0, -1.0),))

    # TODO: 第二段演示（实现后补）
    # 把 FlatIndex 扩成以空间划分树为核心之后，在这里加一段演示：用固定种子造
    # 一批随机矩形建树，做一次点查询、一次矩形相交与一次最近邻，并把访问节点数
    # 与线性扫描的矩形数摆在一起，说明查询已经不再扫全部矩形。


if __name__ == "__main__":
    main()
