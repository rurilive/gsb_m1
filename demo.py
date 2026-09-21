"""jqplan 现状演示。

第一段：三张表按声明顺序执行，看结果和探测行数。
第二段：同一条查询换一个手写的执行顺序，结果一样，探测行数差很多。
第三段：看一眼统计快照。
末尾留了规划器的演示位子（见文末注释）。
"""

import random

from jqplan.engine import Engine, Plan, Query
from jqplan.planner import Planner
from jqplan.stats import Stats
from jqplan.table import Table


def build_tables():
    rng = random.Random(7)
    users = Table("users", ["uid", "city"])
    users.insert_many([(uid, rng.choice(["bj", "sh", "gz", "hz"])) for uid in range(10)])
    orders = Table("orders", ["oid", "uid", "amount"])
    orders.insert_many(
        [(oid, rng.randrange(100), rng.randrange(10, 500)) for oid in range(1000)]
    )
    items = Table("items", ["sku", "oid", "price"])
    items.insert_many(
        [(f"s{i:04d}", i, rng.randrange(1, 100)) for i in range(300)]
    )
    return users, orders, items


def main():
    users, orders, items = build_tables()
    query = Query(
        [items, orders, users],
        [
            ("orders", "oid", "items", "oid"),
            ("users", "uid", "orders", "uid"),
        ],
    )
    engine = Engine()

    print("=== 按声明顺序执行 ===")
    print(f"  声明顺序: {query.table_names()}")
    by_declared = engine.execute(query)
    print(f"  结果 {len(by_declared.rows)} 行，探测 {by_declared.rows_scanned} 行")
    for row in by_declared.rows[:2]:
        print(f"    {row}")

    print("=== 换一个执行顺序 ===")
    by_manual = engine.execute_plan(query, Plan(("users", "orders", "items")))
    print(f"  手写顺序: {by_manual.order}")
    print(f"  结果 {len(by_manual.rows)} 行，探测 {by_manual.rows_scanned} 行")
    print(f"  两次结果一致: {sorted(by_declared.rows) == sorted(by_manual.rows)}")
    first_declared = by_declared.rows[0]
    print(f"  结果行按声明列序输出，第一条: {first_declared}")

    print("=== 统计快照 ===")
    stats = Stats.collect([users, orders, items])
    print(f"  覆盖: {stats.table_names()}")
    for table in (users, orders, items):
        distincts = ", ".join(
            f"{column}: {stats.distinct(table.name, column)}"
            for column in table.columns
        )
        print(f"  {table.name}: rows={stats.row_count(table.name)} distinct=[{distincts}]")
    print(f"  过期表: {stats.stale([users, orders, items])}")
    print(f"  规划器默认计划: {Planner().plan(query).order}")

    # TODO(连接顺序规划): 代价规划落地后，在这里加一段演示：
    # 让 Planner 拿着上面的统计挑顺序，跟手写顺序、穷举最优比探测行数，
    # 再拿十几张表看一眼规划耗时，以及统计过期时计划怎么退化。

    print("=== 完 ===")


if __name__ == "__main__":
    main()
