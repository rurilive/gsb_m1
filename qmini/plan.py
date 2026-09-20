"""计划树：过滤谓词与物理计划结点。

执行模型是迭代器（火山模型）：每个计划结点可迭代，逐行向子结点
拉数据，过滤、排序、投影在拉取过程中完成。explain() 把树打印成
缩进文本，根结点在最上面，越深越靠近数据源。
"""

import operator

COMPARE_OPS = ("=", "!=", ">", ">=", "<", "<=")

_OP_FUNCS = {
    "=": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def format_literal(value):
    """字面量的展示形式：字符串加单引号，其余用 repr。"""
    if isinstance(value, str):
        return "'" + value + "'"
    return repr(value)


class Predicate:
    """过滤条件。子类实现 eval(row) 与 render()（explain 用）。"""

    def eval(self, row):
        raise NotImplementedError

    def render(self):
        raise NotImplementedError


class Compare(Predicate):
    """叶子条件：某列与字面量的比较，是最小的过滤单元。"""

    def __init__(self, op, column, value):
        self.op = op        # COMPARE_OPS 之一，即 _OP_FUNCS 的键
        self.column = column
        self.value = value

    def eval(self, row):
        return _OP_FUNCS[self.op](row[self.column], self.value)

    def render(self):
        return "%s %s %s" % (self.column, self.op, format_literal(self.value))


class And(Predicate):
    """合取结点：所有子条件都为真才为真，子条件按顺序短路求值。"""

    def __init__(self, children):
        self.children = list(children)

    def eval(self, row):
        return all(child.eval(row) for child in self.children)

    def render(self):
        parts = []
        for child in self.children:
            text = child.render()
            if isinstance(child, Or):
                text = "(" + text + ")"
            parts.append(text)
        return " AND ".join(parts)


class Or(Predicate):
    """析取结点：任一子条件为真即为真，子条件按顺序短路求值。"""

    def __init__(self, children):
        self.children = list(children)

    def eval(self, row):
        return any(child.eval(row) for child in self.children)

    def render(self):
        return " OR ".join(child.render() for child in self.children)


class PlanNode:
    """计划结点基类：可迭代，产出行 dict。

    子类设置 self.child（数据来源结点，SeqScan 没有），并实现
    _rows() 与 label()。explain() 缺省按「自身一行 + 子树缩进」打印。
    """

    def __init__(self, child=None):
        self.child = child

    def __iter__(self):
        return self._rows()

    def rows(self):
        """物化全部输出行。"""
        return list(self)

    def _rows(self):
        raise NotImplementedError

    def label(self):
        raise NotImplementedError

    def explain(self, depth=0):
        lines = ["  " * depth + self.label()]
        if self.child is not None:
            lines.extend(self.child.explain(depth + 1))
        return lines


class SeqScan(PlanNode):
    """全表扫描：逐行产出注册表里的 dict（不拷贝，下游不得改写）。"""

    def __init__(self, table_name, rows):
        PlanNode.__init__(self)
        self.table_name = table_name
        self._rows_list = rows

    def _rows(self):
        for row in self._rows_list:
            yield row

    def label(self):
        return "SeqScan[table=%s]" % self.table_name


class FilterNode(PlanNode):
    """逐行用谓词筛选子结点的输出，谓词为假的行被丢弃。"""

    def __init__(self, child, predicate):
        PlanNode.__init__(self, child)
        self.predicate = predicate

    def _rows(self):
        for row in self.child:
            if self.predicate.eval(row):
                yield row

    def label(self):
        return "Filter[%s]" % self.predicate.render()


class SortNode(PlanNode):
    """按键列排序，ASC 缺省。排序稳定：键相同的行保持原有先后。"""

    def __init__(self, child, key, desc=False):
        PlanNode.__init__(self, child)
        self.key = key
        self.desc = desc

    def _rows(self):
        rows = list(self.child)
        rows.sort(key=lambda r: r[self.key], reverse=self.desc)
        return iter(rows)

    def label(self):
        return "Sort[key=%s %s]" % (self.key, "DESC" if self.desc else "ASC")


class ProjectNode(PlanNode):
    """列裁剪：每行重建一个只含所选列的新 dict，'*' 拷贝整行。"""

    def __init__(self, child, columns):
        PlanNode.__init__(self, child)
        self.columns = columns  # ["*"] 表示全部列

    def _rows(self):
        for row in self.child:
            if self.columns == ["*"]:
                yield dict(row)
            else:
                yield dict((c, row[c]) for c in self.columns)

    def label(self):
        return "Project[cols=%s]" % ", ".join(self.columns)


class LimitNode(PlanNode):
    """截断：最多向下游放行 count 行，之后停止拉取。"""

    def __init__(self, child, count):
        PlanNode.__init__(self, child)
        self.count = count

    def _rows(self):
        if self.count <= 0:
            return
        for i, row in enumerate(self.child):
            yield row
            if i + 1 >= self.count:
                return

    def label(self):
        return "Limit[n=%d]" % self.count
