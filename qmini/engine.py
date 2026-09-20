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


def build_plan(stmt, tables):
    """按 FROM -> WHERE -> ORDER BY -> 投影 -> LIMIT 自底向上搭树。

    排序在投影之前，所以 ORDER BY 的列可以不出现在 SELECT 里。
    WHERE 条件树先做等值下推（见 _pushdown_equalities），可能叠出
    两个 Filter：等值条件的在下、更靠近 SeqScan 先求值。
    """
    if stmt.table not in tables:
        raise KeyError(stmt.table)
    node = SeqScan(stmt.table, tables[stmt.table])
    for predicate in _pushdown_equalities(stmt.where):
        node = FilterNode(node, predicate)
    if stmt.order_by is not None:
        node = SortNode(node, stmt.order_by, stmt.desc)
    node = ProjectNode(node, stmt.columns)
    if stmt.limit is not None:
        node = LimitNode(node, stmt.limit)
    return node


def _flatten_and(predicate):
    """把顶层嵌套的 And 拍平成合取项列表；非 And 条件是单项列表。"""
    if isinstance(predicate, And):
        items = []
        for part in predicate.parts:
            items.extend(_flatten_and(part))
        return items
    return [predicate]


def _is_equality(predicate):
    return isinstance(predicate, Compare) and predicate.op == "="


def _combine(parts):
    return parts[0] if len(parts) == 1 else And(parts)


def _pushdown_equalities(predicate):
    """等值条件下推：返回自底向上（靠近 SeqScan 在前）的 Filter 谓词序列。

    顶层是 And 时先拍平，再把列 = 字面量的等值比较拆成一组放在下层
    先求值；其余条件（范围、!=、OR 子树）保持原有相对顺序在上层。
    任一组为空则不生成该层；OR 子树内部的 And 不拆。
    """
    if predicate is None:
        return []
    conjuncts = _flatten_and(predicate)
    if len(conjuncts) == 1:
        return [predicate]
    equalities = [p for p in conjuncts if _is_equality(p)]
    rest = [p for p in conjuncts if not _is_equality(p)]
    if not equalities or not rest:
        return [_combine(conjuncts)]
    return [_combine(equalities), _combine(rest)]
