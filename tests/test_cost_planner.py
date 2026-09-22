"""代价规划的测试。

- 有统计时按估计代价重排，小表集对拍穷举最优，实际探测行数不超两倍
- 十一张表规划一秒内出结果
- 连接组识别与组间叉乘
- 统计缺失、过期、缺列基数时整体退回声明顺序
- 同样的查询加同样的统计，计划确定
"""

import itertools
import random
import time
import unittest

from jqplan.engine import Engine, Plan, Query
from jqplan.planner import Planner
from jqplan.stats import Stats
from jqplan.table import Table


def make_demo_tables():
    """订单远多于用户、连接键扎堆的场景。"""
    rng = random.Random(7)
    users = Table("users", ["uid", "city"])
    users.insert_many([(uid, rng.choice(["bj", "sh", "gz", "hz"])) for uid in range(10)])
    orders = Table("orders", ["oid", "uid", "amount"])
    orders.insert_many(
        [(oid, rng.randrange(100), rng.randrange(10, 500)) for oid in range(1000)]
    )
    items = Table("items", ["sku", "oid", "price"])
    items.insert_many([(f"s{i:04d}", i, rng.randrange(1, 100)) for i in range(300)])
    return users, orders, items


def make_chain_tables(count, seed, sizes=(5, 10, 20, 40)):
    """一条链：t0.k = t1.k, t1.k = t2.k, ...，行数与基数刻意拉开。

    表积控制在十万级，穷举全排列对拍才跑得完。
    """
    rng = random.Random(seed)
    tables = []
    key_space = 12
    for i in range(count):
        table = Table(f"t{i}", ["k", "v"])
        size = sizes[i % len(sizes)]
        table.insert_many(
            [(rng.randrange(key_space), rng.randrange(1000)) for _ in range(size)]
        )
        tables.append(table)
    joins = [(f"t{i}", "k", f"t{i+1}", "k") for i in range(count - 1)]
    return tables, joins


def brute_force_best(engine, query):
    """穷举全排列，返回最小的实际探测行数。"""
    return min(
        engine.execute_plan(query, Plan(perm)).rows_scanned
        for perm in itertools.permutations(query.table_names())
    )


class ReorderTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.planner = Planner()

    def test_reorders_skewed_join_and_stays_near_optimal(self):
        users, orders, items = make_demo_tables()
        query = Query(
            [items, orders, users],
            [
                ("orders", "oid", "items", "oid"),
                ("users", "uid", "orders", "uid"),
            ],
        )
        stats = Stats.collect([users, orders, items])
        plan = self.planner.plan(query, stats)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))
        planned = self.engine.execute_plan(query, plan)
        declared = self.engine.execute(query)
        self.assertEqual(sorted(planned.rows), sorted(declared.rows))
        best = brute_force_best(self.engine, query)
        self.assertLessEqual(planned.rows_scanned, best * 2)
        self.assertLess(planned.rows_scanned, declared.rows_scanned)

    def test_random_chains_stay_within_two_times_optimal(self):
        for seed in (1, 2, 3):
            tables, joins = make_chain_tables(4, seed)
            rng = random.Random(seed + 100)
            shuffled = list(tables)
            rng.shuffle(shuffled)
            query = Query(shuffled, joins)
            stats = Stats.collect(tables)
            plan = self.planner.plan(query, stats)
            planned = self.engine.execute_plan(query, plan)
            best = brute_force_best(self.engine, query)
            self.assertLessEqual(
                planned.rows_scanned,
                best * 2,
                f"seed={seed}: {planned.rows_scanned} vs best {best}",
            )

    def test_star_query_stays_within_two_times_optimal(self):
        rng = random.Random(11)
        fact = Table("fact", ["k1", "k2", "k3", "k4"])
        fact.insert_many(
            [tuple(rng.randrange(15) for _ in range(4)) for _ in range(200)]
        )
        dims = []
        joins = []
        for i in range(1, 4):
            dim = Table(f"dim{i}", ["k", "label"])
            dim.insert_many([(k, f"d{i}_{k}") for k in range(15)])
            dims.append(dim)
            joins.append(("fact", f"k{i}", f"dim{i}", "k"))
        tables = [fact] + dims
        query = Query(tables, joins)
        stats = Stats.collect(tables)
        plan = self.planner.plan(query, stats)
        planned = self.engine.execute_plan(query, plan)
        best = brute_force_best(self.engine, query)
        self.assertLessEqual(planned.rows_scanned, best * 2)


class ScaleTest(unittest.TestCase):
    def test_eleven_tables_plan_within_one_second(self):
        tables, joins = make_chain_tables(11, 99, sizes=(20, 50, 200, 800))
        query = Query(tables, joins)
        stats = Stats.collect(tables)
        start = time.perf_counter()
        plan = Planner().plan(query, stats)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))


class ComponentsTest(unittest.TestCase):
    def setUp(self):
        self.planner = Planner()

    def test_components_split_disconnected_groups(self):
        a = Table("a", ["x"])
        b = Table("b", ["x"])
        c = Table("c", ["x"])
        d = Table("d", ["x"])
        e = Table("e", ["x"])
        query = Query(
            [a, b, c, d, e],
            [("a", "x", "b", "x"), ("b", "x", "c", "x"), ("d", "x", "e", "x")],
        )
        self.assertEqual(
            self.planner.components(query), (("a", "b", "c"), ("d", "e"))
        )

    def test_components_single_table_per_group_without_joins(self):
        a = Table("a", ["x"])
        b = Table("b", ["x"])
        query = Query([a, b], [])
        self.assertEqual(self.planner.components(query), (("a",), ("b",)))

    def test_plan_keeps_components_contiguous(self):
        big = Table("big", ["x", "v"])
        big.insert_many([(i % 10, i) for i in range(500)])
        small = Table("small", ["x", "w"])
        small.insert_many([(i, f"s{i}") for i in range(10)])
        lone_a = Table("lone_a", ["y"])
        lone_a.insert_many([(i,) for i in range(3)])
        lone_b = Table("lone_b", ["z"])
        lone_b.insert_many([(i,) for i in range(4)])
        query = Query(
            [big, lone_a, small, lone_b],
            [("big", "x", "small", "x")],
        )
        stats = Stats.collect([big, small, lone_a, lone_b])
        plan = self.planner.plan(query, stats)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))
        positions = {name: plan.order.index(name) for name in plan.order}
        group = sorted([positions["big"], positions["small"]])
        self.assertEqual(group, list(range(group[0], group[0] + 2)))


class FallbackTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders, self.items = make_demo_tables()
        self.query = Query(
            [self.items, self.orders, self.users],
            [
                ("orders", "oid", "items", "oid"),
                ("users", "uid", "orders", "uid"),
            ],
        )
        self.declared = self.query.table_names()
        self.planner = Planner()

    def test_missing_table_falls_back(self):
        stats = Stats.collect([self.users, self.orders])
        self.assertEqual(self.planner.plan(self.query, stats).order, self.declared)

    def test_stale_stats_fall_back(self):
        stats = Stats.collect([self.users, self.orders, self.items])
        self.users.insert((10, "bj"))
        self.assertEqual(self.planner.plan(self.query, stats).order, self.declared)

    def test_missing_join_column_distinct_falls_back(self):
        stats = Stats.collect([self.users, self.orders, self.items])
        broken = Stats(
            {
                name: {
                    "rows": stats.row_count(name),
                    "distinct": {
                        column: stats.distinct(name, column)
                        for column in ("uid", "city")
                        if stats.distinct(name, column) is not None
                    },
                    "revision": stats.revision(name),
                }
                for name in stats.table_names()
            }
        )
        self.assertEqual(self.planner.plan(self.query, broken).order, self.declared)

    def test_empty_table_does_not_break_planning(self):
        empty = Table("empty", ["x"])
        query = Query(
            [self.users, empty],
            [("users", "uid", "empty", "x")],
        )
        stats = Stats.collect([self.users, empty])
        plan = self.planner.plan(query, stats)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))


class DeterminismTest(unittest.TestCase):
    def test_same_query_same_stats_same_plan(self):
        users, orders, items = make_demo_tables()
        query = Query(
            [items, orders, users],
            [
                ("orders", "oid", "items", "oid"),
                ("users", "uid", "orders", "uid"),
            ],
        )
        stats = Stats.collect([users, orders, items])
        first = Planner().plan(query, stats)
        second = Planner().plan(query, stats)
        again = Planner().plan(query, Stats.collect([users, orders, items]))
        self.assertEqual(first, second)
        self.assertEqual(first, again)


if __name__ == "__main__":
    unittest.main()
