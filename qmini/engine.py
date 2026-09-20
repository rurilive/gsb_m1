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
    WHERE 顶层是 AND 时做等值下推，见 _push_down_equality。
    """
    if stmt.table not in tables:
        raise KeyError(stmt.table)
    node = SeqScan(stmt.table, tables[stmt.table])
    if stmt.where is not None:
        node = _push_down_equality(node, stmt.where)
    if stmt.order_by is not None:
        node = SortNode(node, stmt.order_by, stmt.desc)
    node = ProjectNode(node, stmt.columns)
    if stmt.limit is not None:
        node = LimitNode(node, stmt.limit)
    return node


def _flatten_and(predicate):
    """把顶层 AND 链（含嵌套 AND）摊平成子条件列表，保持原有顺序。

    只展开 AND 自身；OR 子树整体作为一个子条件保留，其内部不动。
    """
    if not isinstance(predicate, And):
        return [predicate]
    flat = []
    for child in predicate.children:
        flat.extend(_flatten_and(child))
    return flat


def _is_equality(predicate):
    return isinstance(predicate, Compare) and predicate.op == "="


def _rejoin(conditions):
    """子条件列表还原成谓词：单个直接用，多个重新合成 AND。"""
    if len(conditions) == 1:
        return conditions[0]
    return And(conditions)


def _push_down_equality(node, predicate):
    """等值条件下推：顶层 AND 拆成等值组与其余组，各包一层 Filter。

    等值比较（列 = 字面量）的 Filter 更靠近 SeqScan 先求值；其余条件
    （范围、!=、OR 子树）保持原有相对顺序叠在其上。某一组为空则不生成
    该层；顶层不是 AND 时保持单 Filter 不变。
    """
    if not isinstance(predicate, And):
        return FilterNode(node, predicate)
    equalities = []
    rest = []
    for cond in _flatten_and(predicate):
        (equalities if _is_equality(cond) else rest).append(cond)
    if equalities:
        node = FilterNode(node, _rejoin(equalities))
    if rest:
        node = FilterNode(node, _rejoin(rest))
    return node
