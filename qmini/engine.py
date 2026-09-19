"""Engine：把 parse -> 计划构建 -> 迭代执行 串起来。"""

from qmini.plan import (And, Compare, FilterNode, LimitNode, ProjectNode,
                        SeqScan, SortNode)
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


def _flatten_and(predicate):
    """顶层是 AND 时取其扁平合取项；嵌套 AND 一并摊平，其余原样返回。"""
    if isinstance(predicate, And):
        items = []
        for child in predicate.children:
            items.extend(_flatten_and(child))
        return items
    return [predicate]


def _stack_filters(node, predicates):
    """按列表顺序自底向上叠 Filter；空列表不加层，单项不包 AND。"""
    if not predicates:
        return node
    condition = predicates[0] if len(predicates) == 1 else And(predicates)
    return FilterNode(node, condition)


def _pushdown_equalities(node, where):
    """等值条件下推。

    顶层 AND 摊平后，把「列 = 字面量」的等值比较单独拆一层，叠在剩余
    条件之下、更靠近 SeqScan 先求值；两组各自保持原有相对顺序。
    OR 子树内的 AND 不摊平（_flatten_and 只处理顶层）。
    """
    conjuncts = _flatten_and(where)
    equalities = [p for p in conjuncts
                  if isinstance(p, Compare) and p.op == "="]
    others = [p for p in conjuncts
              if not (isinstance(p, Compare) and p.op == "=")]
    node = _stack_filters(node, equalities)
    node = _stack_filters(node, others)
    return node


def build_plan(stmt, tables):
    """按 FROM -> WHERE -> ORDER BY -> 投影 -> LIMIT 自底向上搭树。

    WHERE 先走等值下推（见 _pushdown_equalities）；排序在投影之前，
    所以 ORDER BY 的列可以不出现在 SELECT 里。explain 与执行共用
    这一棵树。
    """
    if stmt.table not in tables:
        raise KeyError(stmt.table)
    node = SeqScan(stmt.table, tables[stmt.table])
    if stmt.where is not None:
        node = _pushdown_equalities(node, stmt.where)
    if stmt.order_by is not None:
        node = SortNode(node, stmt.order_by, stmt.desc)
    node = ProjectNode(node, stmt.columns)
    if stmt.limit is not None:
        node = LimitNode(node, stmt.limit)
    return node
