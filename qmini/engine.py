"""Engine：把 parse -> 计划构建 -> 迭代执行 串起来。"""

from qmini.plan import FilterNode, LimitNode, ProjectNode, SeqScan, SortNode
from qmini.sql import parse


class Engine:
    """单机内存表的查询入口。

    register() 存的是调用方传进来的列表引用，不拷贝；每次执行时
    按表名取当前注册的内容搭计划。
    """

    def __init__(self):
        self._tables = {}

    def register(self, name, rows):
        """注册一张表。rows 必须是 list[dict]，重复注册按覆盖处理。"""
        if not isinstance(rows, list):
            raise TypeError("表必须是 list[dict]")
        self._tables[name] = rows

    def _plan(self, sql):
        return build_plan(parse(sql), self._tables)

    def execute(self, sql):
        """执行查询，物化返回全部输出行。"""
        return self._plan(sql).rows()

    def explain(self, sql):
        """返回计划树的缩进文本（不带末尾换行）。"""
        return "\n".join(self._plan(sql).explain())


def build_plan(stmt, tables):
    """按 FROM -> WHERE -> ORDER BY -> 投影 -> LIMIT 自底向上搭树。

    排序在投影之前，所以 ORDER BY 的列可以不出现在 SELECT 里。
    """
    if stmt.table not in tables:
        raise KeyError(stmt.table)
    node = SeqScan(stmt.table, tables[stmt.table])
    if stmt.where is not None:
        node = FilterNode(node, stmt.where)
    if stmt.order_by is not None:
        node = SortNode(node, stmt.order_by, stmt.desc)
    node = ProjectNode(node, stmt.columns)
    if stmt.limit is not None:
        node = LimitNode(node, stmt.limit)
    return node
