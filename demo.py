"""qmini 现状演示：注册表 -> 查询 -> explain。

第一段：单条件过滤加排序。
第二段：排序加截断，顺带看 explain 的树形输出。
"""

from qmini import Engine

USERS = [
    {"name": "alice", "age": 34, "city": "bj", "dept": "core"},
    {"name": "bob", "age": 28, "city": "sh", "dept": "edge"},
    {"name": "carol", "age": 41, "city": "bj", "dept": "core"},
    {"name": "dave", "age": 28, "city": "gz", "dept": "edge"},
    {"name": "erin", "age": 22, "city": "bj", "dept": "core"},
]

ORDERS = [
    {"order_id": 1001, "user": "alice", "amount": 128},
    {"order_id": 1002, "user": "bob", "amount": 66},
    {"order_id": 1003, "user": "carol", "amount": 92},
    {"order_id": 1004, "user": "dave", "amount": 45},
    {"order_id": 1005, "user": "erin", "amount": 158},
]


def show(engine, sql):
    print("SQL> " + sql)
    print(engine.explain(sql))
    for row in engine.execute(sql):
        print("  ", row)
    print()


def main():
    engine = Engine()
    engine.register("users", USERS)
    engine.register("orders", ORDERS)

    print("=== 单条件过滤 ===")
    show(engine, "SELECT name, age FROM users WHERE city = 'bj' ORDER BY age DESC")

    print("=== 过滤 + 排序 + 截断 ===")
    show(engine, "SELECT * FROM orders WHERE amount > 80 ORDER BY amount DESC LIMIT 2")

    print("=== 嵌套条件 + 等值下推 ===")
    # 等值条件 city/dept 被拆到下层 Filter、靠近 SeqScan 先求值，
    # 括号里的 OR 子树保持原样留在上层 Filter。
    show(engine, "SELECT name, age FROM users WHERE city = 'bj' "
                 "AND dept = 'core' AND (age >= 30 OR name = 'erin') "
                 "ORDER BY age DESC")


if __name__ == "__main__":
    main()
