"""Engine：把 parse -> 计划构建（含等值下推）-> 迭代执行 串起来。"""

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
    WHERE 经 _where_layers 可能拆成多个 Filter（等值下推）。
    """
    if stmt.table not in tables:
        raise KeyError(stmt.table)
    node = SeqScan(stmt.table, tables[stmt.table])
    for predicate in _where_layers(stmt.where):
        node = FilterNode(node, predicate)
    if stmt.order_by is not None:
        node = SortNode(node, stmt.order_by, stmt.desc)
    node = ProjectNode(node, stmt.columns)
    if stmt.limit is not None:
        node = LimitNode(node, stmt.limit)
    return node


def _flatten_and(predicate):
    """把顶层连续的 AND 摊平成条件列表；OR 子树内部不展开。"""
    if isinstance(predicate, And):
        return _flatten_and(predicate.left) + _flatten_and(predicate.right)
    return [predicate]


def _fold_and(parts):
    """把条件列表按原顺序左结合回 AND 树；单条件直接返回自身。"""
    pred = parts[0]
    for part in parts[1:]:
        pred = And(pred, part)
    return pred


def _where_layers(predicate):
    """WHERE 的过滤层，按自底向上（先生效）的顺序返回。

    等值下推：条件树顶层是 AND 时先摊平，把「列 = 字面量」的比较
    单独聚成一层放在更靠近 SeqScan 的位置先求值；其余条件（范围、
    !=、OR 子树）保持相对顺序叠在上面。某组为空则不生成该层，只剩
    一组时保持单 Filter；顶层不是 AND 时原样单层。
    """
    if predicate is None:
        return []
    if not isinstance(predicate, And):
        return [predicate]
    equalities, rest = [], []
    for part in _flatten_and(predicate):
        if isinstance(part, Compare) and part.op == "=":
            equalities.append(part)
        else:
            rest.append(part)
    layers = []
    if equalities:
        layers.append(_fold_and(equalities))
    if rest:
        layers.append(_fold_and(rest))
    return layers
