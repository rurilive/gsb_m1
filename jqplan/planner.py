"""连接顺序规划。

Planner.plan 现在直接把查询的声明顺序原样包成 Plan，stats 参数收下了还没用上。
"""

from .engine import Plan


class Planner:
    """给出查询的执行计划。"""

    def plan(self, query, stats=None):
        """按声明顺序出计划。stats 传 None 表示没有统计可用。"""
        return Plan(query.table_names())

    def __repr__(self):
        return "Planner()"
