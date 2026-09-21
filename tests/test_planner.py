"""规划器基线。

没有统计可用时，计划就是查询的声明顺序；这条同时是原执行入口的行为。
"""

import unittest

from jqplan.engine import Engine, Plan
from jqplan.planner import Planner

from test_engine import make_query, make_tables


class PlannerTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders, self.items = make_tables()
        self.query = make_query(self.users, self.orders, self.items)
        self.engine = Engine()

    def test_plan_without_stats_follows_declared_order(self):
        planner = Planner()
        self.assertEqual(
            planner.plan(self.query).order, ("users", "orders", "items")
        )
        self.assertEqual(
            planner.plan(self.query, stats=None).order, ("users", "orders", "items")
        )

    def test_plan_is_a_plan_object(self):
        plan = Planner().plan(self.query)
        self.assertIsInstance(plan, Plan)
        self.assertEqual(plan.order, self.query.table_names())

    def test_execute_matches_planned_execution_without_stats(self):
        planned = self.engine.execute_plan(self.query, Planner().plan(self.query))
        direct = self.engine.execute(self.query)
        self.assertEqual(planned.rows, direct.rows)
        self.assertEqual(planned.rows_scanned, direct.rows_scanned)


if __name__ == "__main__":
    unittest.main()
