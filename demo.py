"""planopt 现状演示。

第一段：造两张表做一次简单的过滤与聚合，看看现在是怎么跑的、统计里读了多少行；
第二段：预留的优化演示位子（谓词下推、投影裁剪、连接顺序、代价对比，见文末注释）。
"""

from planopt.table import Table
from planopt.exec import Query, execute


def main():
    print("=== 朴素执行 ===")
    people = Table(
        "people",
        [
            {"id": 1, "name": "ann", "city": "beijing", "age": 30},
            {"id": 2, "name": "bob", "city": "shanghai", "age": 25},
            {"id": 3, "name": "cy", "city": "beijing", "age": 40},
        ],
    )
    city2 = Table(
        "city2",
        [
            {"city": "beijing", "region": "north"},
            {"city": "shanghai", "region": "east"},
        ],
    )

    query = (
        Query(people)
        .join(city2, "city", "city")
        .where(lambda r: r["region"] == "north")
        .select(["name", "age"])
    )
    table, stats = execute(query)
    print("  结果 %s" % (table.to_dicts(),))
    print("  统计 %s" % (stats,))

    print("=== 计划 ===")
    print(query.explain())

    # TODO(优化与代价): 在 planopt 里补出逻辑计划、谓词下推、投影裁剪、连接顺序
    # 枚举与代价模型之后，在这里加第二段演示：同一条查询分别打印优化前后的计划树、
    # 估计基数与代价，并对比执行统计里的扫描行数，说明下推与裁剪把多少工作省掉了；
    # 再给一个两表以上的连接，展示连接顺序按基数从小到大挑，且结果与朴素执行对拍一致。


if __name__ == "__main__":
    main()