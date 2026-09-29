"""columnkit 现状演示。

第一段：造一张订单表，用谓词过滤出北京的行，看到行数与列；
第二段：预留的执行计划、投影裁剪、哈希连接与聚合演示位子（见文末注释）。
"""

from columnkit.table import Table


def main():
    print("=== 行式过滤 ===")
    orders = Table(
        "orders",
        [
            {"id": 1, "city": "beijing", "amount": 30},
            {"id": 2, "city": "shanghai", "amount": 10},
            {"id": 3, "city": "beijing", "amount": 20},
        ],
    )
    beijing = orders.filter(lambda r: r["city"] == "beijing")
    print("  原表 %d 行，过滤后 %d 行，列 %s" % (
        orders.count(),
        beijing.count(),
        beijing.columns,
    ))
    print("  过滤结果 %s" % (beijing.to_dicts(),))

    # TODO(执行计划与列式算子): 在 columnkit 里补出谓词下推、投影裁剪、哈希连接、
    # 分组聚合与 explain 之后，在这里加一段演示：对一张订单表按城市分组求和，
    # 与客户表做一次连接，只取需要的列，并打印算子树看谓词落在了哪一层。


if __name__ == "__main__":
    main()