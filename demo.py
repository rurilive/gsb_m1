"""geogrid 现状演示。

第一段：登记一批门店点位，按精确坐标查询。
第二段：全量遍历、球面距离与索引状态。
第三段：预留的范围查询演示位子（见文末注释）。
"""

from geogrid import PointIndex
from geogrid.geo import haversine_m


def main():
    index = PointIndex()
    shops = [
        ("s-1001", 31.2304, 121.4737),
        ("s-1002", 31.2304, 121.4737),
        ("s-1003", 31.2319, 121.4699),
        ("s-1004", 39.9042, 116.4074),
        ("s-1005", -33.8688, 151.2093),
    ]
    for pid, lat, lon in shops:
        index.add(pid, lat, lon)

    print("=== 精确坐标查询 ===")
    print("  at(31.2304, 121.4737) ->", index.at(31.2304, 121.4737))
    print("  at(31.2304, 121.4738) ->", index.at(31.2304, 121.4738))
    print("  同一坐标的两家店一起返回，差一点坐标的不返回")

    print("=== 全量遍历与状态 ===")
    for pid, lat, lon in index.scan():
        print("  %-7s %.4f, %.4f" % (pid, lat, lon))
    print("  上海到北京 %.0f 米" % haversine_m(31.2304, 121.4737, 39.9042, 116.4074))
    print("  stats:", index.stats())

    # TODO(范围查询): box 与 circle 就绪后在这里补一段演示，按矩形捞一个
    # 片区、按圆找三公里内的门店，并打印每次查询访问的格子数。

    print("=== 收尾: points=%d cells=%d ===" % (len(index), index.stats()["cells"]))


if __name__ == "__main__":
    main()
