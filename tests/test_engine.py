"""执行器行为基线。

锁住结果内容、输出列顺序、探测行数的口径，以及计划必须跟查询对得上。
"""

import unittest

from jqplan.engine import Engine, Plan, Query
from jqplan.table import Table


def make_tables():
    users = Table("users", ["uid", "city"])
    users.insert_many([(1, "bj"), (2, "sh"), (3, "bj")])
    orders = Table("orders", ["oid", "uid", "amount"])
    orders.insert_many([(10, 1, 50), (11, 1, 20), (12, 2, 30), (13, 9, 10)])
    items = Table("items", ["sku", "oid"])
    items.insert_many([("a", 10), ("b", 10), ("c", 12), ("d", 99)])
    return users, orders, items


def make_query(users, orders, items, select=None):
    return Query(
        [users, orders, items],
        [
            ("users", "uid", "orders", "uid"),
            ("orders", "oid", "items", "oid"),
        ],
        select=select,
    )


class ExecuteTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders, self.items = make_tables()
        self.query = make_query(self.users, self.orders, self.items)
        self.engine = Engine()

    def test_execute_uses_declared_order(self):
        result = self.engine.execute(self.query)
        self.assertEqual(result.order, ("users", "orders", "items"))

    def test_result_rows_in_declared_column_layout(self):
        result = self.engine.execute(self.query)
        self.assertEqual(
            result.rows,
            [
                (1, "bj", 10, 1, 50, "a", 10),
                (1, "bj", 10, 1, 50, "b", 10),
                (2, "sh", 12, 2, 30, "c", 12),
            ],
        )

    def test_rows_scanned_counts_every_probe(self):
        result = self.engine.execute(self.query)
        self.assertEqual(result.rows_scanned, 3 + 3 * 4 + 3 * 4)

    def test_permuted_plan_same_rows_different_scan(self):
        result = self.engine.execute_plan(
            self.query, Plan(("items", "orders", "users"))
        )
        expected = self.engine.execute(self.query)
        self.assertEqual(sorted(result.rows), sorted(expected.rows))
        self.assertEqual(result.rows_scanned, 4 + 4 * 4 + 3 * 3)
        for row in result.rows:
            self.assertIn(row[0], (1, 2, 3))
            self.assertIn(row[1], ("bj", "sh"))
            self.assertIn(row[5], ("a", "b", "c"))
            self.assertEqual(row[2], row[6])

    def test_select_keeps_requested_order(self):
        query = make_query(
            self.users, self.orders, self.items, select=["items.sku", "users.city"]
        )
        result = self.engine.execute(query)
        self.assertEqual(result.rows, [("a", "bj"), ("b", "bj"), ("c", "sh")])

    def test_empty_table_yields_no_rows(self):
        empty = Table("items", ["sku", "oid"])
        query = make_query(self.users, self.orders, empty)
        result = self.engine.execute(query)
        self.assertEqual(result.rows, [])
        self.assertEqual(result.rows_scanned, 3 + 3 * 4)

    def test_duplicate_table_names_rejected(self):
        with self.assertRaises(ValueError):
            Query([self.users, self.users], [("users", "uid", "users", "uid")])

    def test_unknown_table_or_column_rejected(self):
        with self.assertRaises(ValueError):
            Query(
                [self.users, self.orders],
                [("users", "uid", "ghost", "uid")],
            )
        with self.assertRaises(KeyError):
            Query(
                [self.users, self.orders],
                [("users", "uid", "orders", "nope")],
            )
        with self.assertRaises(ValueError):
            make_query(self.users, self.orders, self.items, select=["ghost.uid"])

    def test_plan_must_match_query_tables(self):
        with self.assertRaises(ValueError):
            self.engine.execute_plan(self.query, Plan(("users", "orders")))
        with self.assertRaises(ValueError):
            self.engine.execute_plan(
                self.query, Plan(("users", "orders", "items", "items"))
            )


if __name__ == "__main__":
    unittest.main()
