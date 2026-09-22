"""代价规划的测试。

锁住：有统计时重排顺序且质量逼近穷举最优、连通组识别与拼接、
统计缺失或过期时退回声明顺序、同查询同统计计划确定、十一张表规划耗时。
"""

import itertools
import time
import unittest

from jqplan.engine import Engine, Plan, Query
from jqplan.planner import Planner
from jqplan.stats import Stats
from jqplan.table import Table


def make_skewed_tables():
    users = Table("users", ["uid", "city"])
    users.insert_many([(uid, f"c{uid % 4}") for uid in range(8)])
    orders = Table("orders", ["oid", "uid", "amount"])
    orders.insert_many([(oid, oid % 8, oid) for oid in range(100)])
    items = Table("items", ["sku", "oid"])
    items.insert_many([(f"s{i}", (i * 7) % 100) for i in range(40)])
    refunds = Table("refunds", ["rid", "oid"])
    refunds.insert_many([(rid, (rid * 13) % 100) for rid in range(10)])
    return users, orders, items, refunds


def make_skewed_query(users, orders, items, refunds):
    return Query(
        [items, refunds, orders, users],
        [
            ("users", "uid", "orders", "uid"),
            ("orders", "oid", "items", "oid"),
            ("orders", "oid", "refunds", "oid"),
        ],
    )


def make_island_tables():
    a1 = Table("a1", ["x", "va"])
    a1.insert_many([(x, f"a{x}") for x in range(8)])
    a2 = Table("a2", ["y", "x"])
    a2.insert_many([(y, y % 8) for y in range(40)])
    b1 = Table("b1", ["z", "vb"])
    b1.insert_many([(z, f"b{z}") for z in range(5)])
    b2 = Table("b2", ["w", "z"])
    b2.insert_many([(w, w % 5) for w in range(60)])
    return a1, a2, b1, b2


def make_island_query(a1, a2, b1, b2):
    return Query(
        [a2, b2, a1, b1],
        [("a1", "x", "a2", "x"), ("b1", "z", "b2", "z")],
    )


def best_scan(query):
    engine = Engine()
    names = query.table_names()
    return min(
        engine.execute_plan(query, Plan(perm)).rows_scanned
        for perm in itertools.permutations(names)
    )


class CostPlanTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders, self.items, self.refunds = make_skewed_tables()
        self.query = make_skewed_query(self.users, self.orders, self.items, self.refunds)
        self.stats = Stats.collect([self.users, self.orders, self.items, self.refunds])
        self.engine = Engine()

    def test_plan_reorders_by_cost(self):
        plan = Planner().plan(self.query, self.stats)
        self.assertIsInstance(plan, Plan)
        self.assertEqual(sorted(plan.order), sorted(self.query.table_names()))
        self.assertNotEqual(plan.order, self.query.table_names())
        self.assertEqual(plan.order, ("refunds", "orders", "items", "users"))

    def test_planned_scan_within_twice_of_brute_force_best(self):
        plan = Planner().plan(self.query, self.stats)
        scanned = self.engine.execute_plan(self.query, plan).rows_scanned
        declared = self.engine.execute(self.query).rows_scanned
        self.assertLessEqual(scanned, 2 * best_scan(self.query))
        self.assertLess(scanned, declared)

    def test_planned_rows_match_declared_execution(self):
        plan = Planner().plan(self.query, self.stats)
        planned = self.engine.execute_plan(self.query, plan)
        direct = self.engine.execute(self.query)
        self.assertEqual(sorted(planned.rows), sorted(direct.rows))

    def test_plan_is_deterministic(self):
        first = Planner().plan(self.query, self.stats)
        again = Planner().plan(self.query, self.stats)
        fresh_stats = Stats.collect([self.users, self.orders, self.items, self.refunds])
        self.assertEqual(first, again)
        self.assertEqual(first, Planner().plan(self.query, fresh_stats))


class FallbackTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders, self.items, self.refunds = make_skewed_tables()
        self.query = make_skewed_query(self.users, self.orders, self.items, self.refunds)
        self.declared = self.query.table_names()

    def test_missing_stats_falls_back(self):
        self.assertEqual(Planner().plan(self.query).order, self.declared)
        self.assertEqual(Planner().plan(self.query, None).order, self.declared)

    def test_stale_stats_falls_back(self):
        stats = Stats.collect([self.users, self.orders, self.items, self.refunds])
        self.orders.insert((4000, 0, 1))
        self.assertEqual(Planner().plan(self.query, stats).order, self.declared)

    def test_partial_stats_falls_back(self):
        stats = Stats.collect([self.users, self.orders, self.items])
        self.assertEqual(Planner().plan(self.query, stats).order, self.declared)

    def test_missing_join_column_distinct_falls_back(self):
        stats = Stats.collect([self.users, self.orders, self.items, self.refunds])
        entries = {
            name: {
                "rows": stats.row_count(name),
                "distinct": {
                    column: stats.distinct(name, column)
                    for column in self.query.table(name).columns
                },
                "revision": stats.revision(name),
            }
            for name in stats.table_names()
        }
        del entries["orders"]["distinct"]["oid"]
        self.assertEqual(Planner().plan(self.query, Stats(entries)).order, self.declared)


class ComponentsTest(unittest.TestCase):
    def setUp(self):
        self.a1, self.a2, self.b1, self.b2 = make_island_tables()
        self.query = make_island_query(self.a1, self.a2, self.b1, self.b2)
        self.stats = Stats.collect([self.a1, self.a2, self.b1, self.b2])
        self.engine = Engine()

    def test_components_groups_disconnected_tables(self):
        self.assertEqual(
            Planner().components(self.query), (("a2", "a1"), ("b2", "b1"))
        )

    def test_components_of_connected_query_is_one_group(self):
        users, orders, items, refunds = make_skewed_tables()
        query = make_skewed_query(users, orders, items, refunds)
        self.assertEqual(Planner().components(query), (query.table_names(),))

    def test_plan_keeps_groups_contiguous_and_orders_within(self):
        plan = Planner().plan(self.query, self.stats)
        self.assertEqual(plan.order, ("a1", "a2", "b1", "b2"))

    def test_cross_product_rows_match_declared_execution(self):
        plan = Planner().plan(self.query, self.stats)
        planned = self.engine.execute_plan(self.query, plan)
        direct = self.engine.execute(self.query)
        self.assertEqual(sorted(planned.rows), sorted(direct.rows))
        self.assertLessEqual(planned.rows_scanned, 2 * best_scan(self.query))


class ScaleTest(unittest.TestCase):
    def test_eleven_tables_plan_within_a_second(self):
        tables = []
        for i in range(11):
            table = Table(f"t{i}", ["k", "v"])
            table.insert_many([(k, k * (i + 1)) for k in range(20 + i * 5)])
            tables.append(table)
        joins = [(f"t{i}", "k", f"t{i + 1}", "k") for i in range(10)]
        query = Query(list(reversed(tables)), joins)
        stats = Stats.collect(tables)
        start = time.monotonic()
        plan = Planner().plan(query, stats)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))


if __name__ == "__main__":
    unittest.main()
