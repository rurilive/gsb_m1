"""qmini: 内存表的迷你查询引擎。

流程：parse(sql) 解析成 SelectStmt，build_plan 搭出计划树，计划结点
本身就是迭代器，执行即遍历树根。SQL 子集、各结点语义与 explain
格式见 README。
"""

from qmini.engine import Engine, build_plan
from qmini.plan import (Compare, FilterNode, LimitNode, PlanNode, Predicate,
                        ProjectNode, SeqScan, SortNode)
from qmini.sql import ParseError, parse

__all__ = [
    "Engine", "ParseError", "Predicate", "Compare", "PlanNode",
    "SeqScan", "FilterNode", "SortNode", "ProjectNode", "LimitNode",
    "build_plan", "parse",
]
