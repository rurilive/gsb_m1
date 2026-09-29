"""朴素执行器与表容器的行为锁定测试（基线，一字不改且必须全绿）。

这些测试锁的是对外可观察的契约：表的构造与只读语义、查询构建链的参数校验、
四类连接的结果与列命名、过滤与投影的列序、聚合的分组顺序，以及 execute 返回
的表与统计。改造之后这些契约必须原样成立，结果与现状逐行一致。
"""

import unittest

from planopt.table import Table
from planopt.exec import ExecStats, Query, execute


PEOPLE = [
    {"id": 1, "name": "ann", "city": "beijing", "age": 30},
    {"id": 2, "name": "bob", "city": "shanghai", "age": 25},
    {"id": 3, "name": "cy", "city": "beijing", "age": 40},
    {"id": 4, "name": "dan", "city": "shenzhen", "age": 35},
]

CITIES = [
    {"city": "beijing", "region": "north"},
    {"city": "shanghai", "region": "east"},
]


def people():
    return Table("people", PEOPLE)


def cities():
    return Table("city2", CITIES)


class TestTable(unittest.TestCase):
    def test_name_and_columns(self):
        t = people()
        self.assertEqual(t.name, "people")
        self.assertEqual(t.columns, ("id", "name", "city", "age"))

    def test_columns_explicit(self):
        t = Table("people", PEOPLE, columns=["age", "id"])
        self.assertEqual(t.columns, ("age", "id"))

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            Table("", PEOPLE)

    def test_non_dict_row_rejected(self):
        with self.assertRaises(ValueError):
            Table("people", [(1, 2, 3)])

    def test_rows_not_aliased(self):
        source = [dict(PEOPLE[0])]
        t = Table("people", source)
        source[0]["age"] = 999
        self.assertEqual(t.to_dicts()[0]["age"], 30)

    def test_count_and_len(self):
        t = people()
        self.assertEqual(t.count(), 4)
        self.assertEqual(len(t), 4)

    def test_filter_keeps_matching(self):
        out = people().filter(lambda r: r["city"] == "beijing")
        self.assertEqual([r["id"] for r in out], [1, 3])

    def test_filter_non_callable_rejected(self):
        with self.assertRaises(ValueError):
            people().filter(5)

    def test_filter_does_not_mutate_source(self):
        people().filter(lambda r: r["age"] > 100)
        self.assertEqual(people().count(), 4)


class TestBuildValidation(unittest.TestCase):
    def test_source_must_be_table(self):
        with self.assertRaises(ValueError):
            Query([{"id": 1}])

    def test_where_requires_callable(self):
        with self.assertRaises(ValueError):
            Query(people()).where("age")

    def test_select_unknown_column(self):
        with self.assertRaises(ValueError):
            Query(people()).select(["nope"])

    def test_select_must_be_sequence(self):
        with self.assertRaises(ValueError):
            Query(people()).select("age")

    def test_join_unknown_left_key(self):
        with self.assertRaises(ValueError):
            Query(people()).join(cities(), "nope", "city")

    def test_join_unknown_right_key(self):
        with self.assertRaises(ValueError):
            Query(people()).join(cities(), "city", "nope")

    def test_join_unknown_kind(self):
        with self.assertRaises(ValueError):
            Query(people()).join(cities(), "city", "city", how="cross")

    def test_group_by_unknown_column(self):
        with self.assertRaises(ValueError):
            Query(people()).group_by(["nope"])

    def test_group_by_twice_rejected(self):
        with self.assertRaises(ValueError):
            Query(people()).group_by(["city"]).group_by(["age"])

    def test_agg_requires_group_by(self):
        with self.assertRaises(ValueError):
            Query(people()).agg("n", "count", None)

    def test_agg_unknown_func(self):
        with self.assertRaises(ValueError):
            Query(people()).group_by(["city"]).agg("n", "median", "age")

    def test_where_after_agg_rejected(self):
        with self.assertRaises(ValueError):
            Query(people()).group_by(["city"]).agg("n", "count", None).where(
                lambda r: True
            )

    def test_join_after_agg_rejected(self):
        with self.assertRaises(ValueError):
            Query(people()).group_by(["city"]).agg("n", "count", None).join(
                cities(), "city", "city"
            )

    def test_select_after_group_by_rejected(self):
        with self.assertRaises(ValueError):
            Query(people()).group_by(["city"]).select(["city"])

    def test_chain_does_not_mutate_original(self):
        base = Query(people())
        filtered = base.where(lambda r: r["age"] > 28)
        self.assertIsNot(base, filtered)
        self.assertEqual(base.run().count(), 4)
        self.assertEqual(filtered.run().count(), 3)

    def test_execute_requires_query(self):
        with self.assertRaises(ValueError):
            execute(people())


class TestFilterProject(unittest.TestCase):
    def test_run_returns_table(self):
        out = Query(people()).run()
        self.assertIsInstance(out, Table)
        self.assertEqual(out.name, "people")
        self.assertEqual(out.columns, ("id", "name", "city", "age"))
        self.assertEqual(out.count(), 4)

    def test_where_filters_rows(self):
        out = Query(people()).where(lambda r: r["age"] > 28).run()
        self.assertEqual([r["id"] for r in out], [1, 3, 4])

    def test_multiple_where_are_conjunctive(self):
        out = (
            Query(people())
            .where(lambda r: r["age"] > 28)
            .where(lambda r: r["city"] == "beijing")
            .run()
        )
        self.assertEqual([r["id"] for r in out], [1, 3])

    def test_select_column_order(self):
        out = Query(people()).select(["name", "age"]).run()
        self.assertEqual(out.columns, ("name", "age"))
        self.assertEqual(out.to_dicts()[0], {"name": "ann", "age": 30})

    def test_later_select_replaces_earlier(self):
        out = Query(people()).select(["id", "age"]).select(["age"]).run()
        self.assertEqual(out.columns, ("age",))


class TestJoin(unittest.TestCase):
    def test_inner_join_rows_and_columns(self):
        out = Query(people()).join(cities(), "city", "city").run()
        self.assertEqual(
            out.columns, ("id", "name", "city", "age", "city2_city", "region")
        )
        self.assertEqual([r["id"] for r in out], [1, 2, 3])
        self.assertEqual(out.to_dicts()[0]["region"], "north")
        self.assertEqual(out.to_dicts()[0]["city2_city"], "beijing")

    def test_left_join_fills_none(self):
        out = Query(people()).join(cities(), "city", "city", how="left").run()
        self.assertEqual([r["id"] for r in out], [1, 2, 3, 4])
        self.assertIsNone(out.to_dicts()[3]["region"])
        self.assertIsNone(out.to_dicts()[3]["city2_city"])

    def test_right_join_rows(self):
        out = Query(people()).join(cities(), "city", "city", how="right").run()
        self.assertEqual([r["id"] for r in out], [1, 3, 2])

    def test_full_join_rows(self):
        out = Query(people()).join(cities(), "city", "city", how="full").run()
        self.assertEqual([r["id"] for r in out], [1, 2, 3, 4])

    def test_duplicate_keys_multiply_rows(self):
        left = Table("l", [{"k": 1, "a": "x"}, {"k": 1, "a": "y"}])
        right = Table("r", [{"k": 1, "b": "p"}, {"k": 1, "b": "q"}])
        out = Query(left).join(right, "k", "k").run()
        self.assertEqual(out.count(), 4)
        self.assertEqual(
            [(r["a"], r["b"]) for r in out],
            [("x", "p"), ("x", "q"), ("y", "p"), ("y", "q")],
        )

    def test_join_then_where(self):
        out = (
            Query(people())
            .join(cities(), "city", "city")
            .where(lambda r: r["region"] == "north")
            .run()
        )
        self.assertEqual([r["id"] for r in out], [1, 3])


class TestAggregate(unittest.TestCase):
    def test_group_count_and_avg(self):
        out = (
            Query(people())
            .group_by(["city"])
            .agg("n", "count", None)
            .agg("avg_age", "avg", "age")
            .run()
        )
        self.assertEqual(out.columns, ("city", "n", "avg_age"))
        self.assertEqual(
            out.to_dicts(),
            [
                {"city": "beijing", "n": 2, "avg_age": 35.0},
                {"city": "shanghai", "n": 1, "avg_age": 25.0},
                {"city": "shenzhen", "n": 1, "avg_age": 35.0},
            ],
        )

    def test_sum_min_max(self):
        out = (
            Query(people())
            .group_by(["city"])
            .agg("total", "sum", "age")
            .agg("lo", "min", "age")
            .agg("hi", "max", "age")
            .run()
        )
        first = out.to_dicts()[0]
        self.assertEqual((first["total"], first["lo"], first["hi"]), (70, 30, 40))

    def test_agg_order_follows_calls(self):
        out = (
            Query(people())
            .group_by(["city"])
            .agg("hi", "max", "age")
            .agg("lo", "min", "age")
            .run()
        )
        self.assertEqual(out.columns, ("city", "hi", "lo"))


class TestExecuteStats(unittest.TestCase):
    def test_execute_returns_table_and_stats(self):
        table, stats = execute(Query(people()))
        self.assertIsInstance(table, Table)
        self.assertIsInstance(stats, ExecStats)
        self.assertEqual(stats.rows_out, table.count())
        self.assertGreaterEqual(stats.scanned, 0)
        self.assertGreaterEqual(stats.probed, 0)

    def test_scan_counts_source_rows(self):
        _, stats = execute(Query(people()))
        self.assertEqual(stats.scanned, 4)


if __name__ == "__main__":
    unittest.main()
