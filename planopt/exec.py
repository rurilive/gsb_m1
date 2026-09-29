"""朴素查询执行器。

现状：Query 是一条固定顺序的算子流水线，扫描、连接、过滤、投影、聚合按
写死的次序逐段执行。连接用嵌套循环逐对比较，过滤条件一律排在连接之后才
生效，读列也是整行读到底。既没有逻辑计划与等价重写，也没有代价模型，
慢在哪里看不出来。
"""

from planopt.table import Table


_HOWS = ("inner", "left", "right", "full")
_AGGS = ("count", "sum", "min", "max", "avg")


class ExecStats:
    """一次执行的工作量统计。

    scanned 是所有扫描节点读出的行数合计，probed 是连接里逐对比较的次数，
    rows_out 是最终结果行数。
    """

    def __init__(self, scanned=0, probed=0, rows_out=0):
        self.scanned = scanned
        self.probed = probed
        self.rows_out = rows_out

    def __repr__(self):
        return "ExecStats(scanned=%d, probed=%d, rows_out=%d)" % (
            self.scanned,
            self.probed,
            self.rows_out,
        )


class Join:
    """查询里记下的一次连接：右侧输入、两侧等值键与连接方式。"""

    def __init__(self, other, left_on, right_on, how):
        self.other = other
        self.left_on = left_on
        self.right_on = right_on
        self.how = how


class Plan:
    """朴素的算子树：只有节点名与子节点，没有代价与基数。"""

    def __init__(self, op, detail="", children=()):
        self.op = op
        self.detail = detail
        self.children = list(children)

    def render(self):
        lines = []
        self._render(0, lines)
        return "\n".join(lines)

    def _render(self, depth, lines):
        head = self.op
        if self.detail:
            head += "(" + self.detail + ")"
        lines.append("  " * depth + head)
        for child in self.children:
            child._render(depth + 1, lines)

    def __str__(self):
        return self.render()


class Query:
    """不可变的查询构建链。

    每一步返回一个新的 Query，原 Query 一个字段都不改。构建时只做参数校验，
    真正的执行留到 run 或 execute 里按固定顺序进行。
    """

    def __init__(self, table):
        if not isinstance(table, Table):
            raise ValueError("query source must be a Table")
        self._table = table
        self._columns = tuple(table.columns)
        self._filters = ()
        self._joins = ()
        self._select = None
        self._group_keys = ()
        self._aggs = ()
        self._grouped = False

    # ---- 构建 ----

    def _copy(self):
        clone = Query.__new__(Query)
        clone._table = self._table
        clone._columns = self._columns
        clone._filters = self._filters
        clone._joins = self._joins
        clone._select = self._select
        clone._group_keys = self._group_keys
        clone._aggs = self._aggs
        clone._grouped = self._grouped
        return clone

    def where(self, predicate):
        if not callable(predicate):
            raise ValueError("predicate must be callable")
        if self._aggs:
            raise ValueError("where is not allowed after agg")
        clone = self._copy()
        clone._filters = self._filters + (predicate,)
        return clone

    def select(self, columns):
        if self._grouped:
            raise ValueError("select is not allowed after group_by")
        if isinstance(columns, str):
            raise ValueError("columns must be a sequence of names")
        cols = tuple(columns)
        for col in cols:
            if col not in self._columns:
                raise ValueError("unknown column: %s" % (col,))
        clone = self._copy()
        clone._select = cols
        clone._columns = cols
        return clone

    def join(self, other, left_on, right_on, how="inner"):
        if self._aggs:
            raise ValueError("join is not allowed after agg")
        if how not in _HOWS:
            raise ValueError("unknown join kind: %s" % (how,))
        if left_on not in self._columns:
            raise ValueError("unknown column: %s" % (left_on,))
        right_cols, right_name = _describe(other)
        if right_on not in right_cols:
            raise ValueError("unknown column: %s" % (right_on,))
        renamed = []
        for col in right_cols:
            if col in self._columns:
                renamed.append(right_name + "_" + col)
            else:
                renamed.append(col)
        clone = self._copy()
        clone._joins = self._joins + (Join(other, left_on, right_on, how),)
        clone._columns = self._columns + tuple(renamed)
        return clone

    def group_by(self, keys):
        if self._grouped:
            raise ValueError("group_by may only be called once")
        if isinstance(keys, str):
            raise ValueError("keys must be a sequence of names")
        keys = tuple(keys)
        for key in keys:
            if key not in self._columns:
                raise ValueError("unknown column: %s" % (key,))
        clone = self._copy()
        clone._group_keys = keys
        clone._grouped = True
        return clone

    def agg(self, name, func, source):
        if not self._grouped:
            raise ValueError("agg requires group_by")
        if func not in _AGGS:
            raise ValueError("unknown aggregate: %s" % (func,))
        if func == "count":
            if source is not None and source not in self._columns:
                raise ValueError("unknown column: %s" % (source,))
        else:
            if not isinstance(source, str) or source not in self._columns:
                raise ValueError("unknown column: %s" % (source,))
        clone = self._copy()
        clone._aggs = self._aggs + ((name, func, source),)
        return clone

    # ---- 计划与执行 ----

    @property
    def output_columns(self):
        if self._aggs:
            return tuple(self._group_keys) + tuple(a[0] for a in self._aggs)
        if self._select is not None:
            return self._select
        return self._columns

    def explain(self):
        node = Plan("Scan", self._table.name)
        for join in self._joins:
            right = _plan_of(join.other)
            node = Plan(
                "Join",
                "%s on %s=%s" % (join.how, join.left_on, join.right_on),
                [node, right],
            )
        for _ in self._filters:
            node = Plan("Filter", "", [node])
        if self._select is not None:
            node = Plan("Project", ",".join(self._select), [node])
        if self._aggs:
            node = Plan(
                "Aggregate", "keys=%s" % ",".join(self._group_keys), [node]
            )
        return node

    def run(self):
        return execute(self)[0]


def _describe(source):
    """给出一个输入的行列与表名。"""
    if isinstance(source, Query):
        return source.output_columns, source._table.name
    if isinstance(source, Table):
        return tuple(source.columns), source.name
    raise ValueError("join input must be a Table or Query")


def _plan_of(source):
    if isinstance(source, Query):
        return source.explain()
    if isinstance(source, Table):
        return Plan("Scan", source.name)
    raise ValueError("join input must be a Table or Query")


def _materialize(source):
    if isinstance(source, Table):
        return source.to_dicts(), tuple(source.columns), ExecStats(
            scanned=source.count()
        )
    if isinstance(source, Query):
        table, stats = execute(source)
        return table.to_dicts(), tuple(table.columns), stats
    raise ValueError("join input must be a Table or Query")


def _merge(left, right, rename, left_cols):
    row = {}
    for col in left_cols:
        row[col] = None if left is None else left.get(col)
    for col, out_col in rename.items():
        row[out_col] = None if right is None else right.get(col)
    return row


def _reduce(func, source, group):
    if func == "count":
        if source is None:
            return len(group)
        return sum(1 for r in group if r.get(source) is not None)
    values = [r.get(source) for r in group if r.get(source) is not None]
    if func == "sum":
        total = 0
        for value in values:
            total += _require_number(value)
        return total
    if func == "avg":
        if not values:
            return None
        total = 0
        for value in values:
            total += _require_number(value)
        return total / len(values)
    if func == "min":
        return min(values) if values else None
    if func == "max":
        return max(values) if values else None
    raise ValueError("unknown aggregate: %s" % (func,))


def _require_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("sum and avg require numeric values")
    return value


def _aggregate(rows, keys, aggs):
    groups = {}
    order = []
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    out = []
    for key in order:
        group = groups[key]
        result = {}
        for col, value in zip(keys, key):
            result[col] = value
        for name, func, source in aggs:
            result[name] = _reduce(func, source, group)
        out.append(result)
    columns = list(keys) + [a[0] for a in aggs]
    return out, columns


def execute(query):
    """按固定顺序执行一条查询，返回结果表与工作量统计。"""
    if not isinstance(query, Query):
        raise ValueError("execute expects a Query")

    rows = [dict(row) for row in query._table]
    cols = list(query._table.columns)
    scanned = len(rows)
    probed = 0

    for join in query._joins:
        right_rows, right_cols, sub = _materialize(join.other)
        scanned += sub.scanned
        renamed = {}
        right_name = _describe(join.other)[1]
        for col in right_cols:
            renamed[col] = right_name + "_" + col if col in cols else col
        new_cols = cols + [renamed[c] for c in right_cols]

        out = []
        if join.how in ("inner", "left", "full"):
            matched = [False] * len(right_rows)
            for left in rows:
                hit = False
                for index, right in enumerate(right_rows):
                    probed += 1
                    if left.get(join.left_on) == right.get(join.right_on):
                        hit = True
                        matched[index] = True
                        out.append(_merge(left, right, renamed, cols))
                if not hit and join.how in ("left", "full"):
                    out.append(_merge(left, None, renamed, cols))
            if join.how == "full":
                for index, right in enumerate(right_rows):
                    if not matched[index]:
                        out.append(_merge(None, right, renamed, cols))
        else:  # right
            for right in right_rows:
                hit = False
                for left in rows:
                    probed += 1
                    if left.get(join.left_on) == right.get(join.right_on):
                        hit = True
                        out.append(_merge(left, right, renamed, cols))
                if not hit:
                    out.append(_merge(None, right, renamed, cols))
        rows = out
        cols = new_cols

    for predicate in query._filters:
        rows = [row for row in rows if predicate(dict(row))]

    if query._select is not None:
        rows = [{c: row.get(c) for c in query._select} for row in rows]
        cols = list(query._select)

    if query._aggs:
        rows, cols = _aggregate(rows, query._group_keys, query._aggs)

    result = Table(query._table.name, rows, cols)
    return result, ExecStats(scanned=scanned, probed=probed, rows_out=len(rows))
