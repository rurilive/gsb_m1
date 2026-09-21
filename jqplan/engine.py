"""查询与执行。

Query 描述一次多表等值连接：参与的表、表间的等值条件、要输出的列。
Engine 按计划给出的表顺序做嵌套循环，某个条件涉及的两张表都进入前缀之后
立刻参与过滤。rows_scanned 记录整个执行过程探测过多少行。
输出列的顺序永远按查询声明走，跟执行顺序无关。
"""


class Query:
    """一次多表等值连接查询。表名在同一次查询里必须唯一。"""

    def __init__(self, tables, joins=(), select=None):
        """
        tables: Table 列表，顺序即声明顺序。
        joins: (左表名, 左列, 右表名, 右列) 列表，都是等值条件。
        select: 要输出的 "表名.列名" 列表，None 表示按声明顺序输出所有列。
        """
        tables = list(tables)
        names = [table.name for table in tables]
        if len(set(names)) != len(names):
            raise ValueError("同一次查询里表名不能重复")
        self._tables = tables
        self._by_name = {table.name: table for table in tables}
        if not self._tables:
            raise ValueError("查询至少要有一张表")
        self._joins = [self._check_join(join) for join in joins]
        self._select = self._check_select(select)

    def _check_join(self, join):
        t1, c1, t2, c2 = join
        if t1 == t2:
            raise ValueError(f"条件两边的表重了: {t1}")
        for name, column in ((t1, c1), (t2, c2)):
            table = self._by_name.get(name)
            if table is None:
                raise ValueError(f"查询里没有表 {name}")
            table.column_index(column)
        return (t1, c1, t2, c2)

    def _check_select(self, select):
        if select is None:
            return tuple(
                f"{table.name}.{column}"
                for table in self._tables
                for column in table.columns
            )
        selected = []
        for item in select:
            name, _, column = item.partition(".")
            table = self._by_name.get(name)
            if not column or table is None:
                raise ValueError(f"输出列 {item} 对不上任何表")
            table.column_index(column)
            selected.append(item)
        return tuple(selected)

    def table_names(self):
        """声明顺序的表名。"""
        return tuple(table.name for table in self._tables)

    def tables(self):
        """声明顺序的表对象。"""
        return tuple(self._tables)

    def table(self, name):
        """按名取表。"""
        return self._by_name[name]

    def joins(self):
        """等值条件，原样返回。"""
        return tuple(self._joins)

    def select(self):
        """输出列，形如 "表名.列名"。"""
        return self._select

    def __repr__(self):
        return f"Query(tables={self.table_names()!r}, joins={len(self._joins)})"


class Plan:
    """执行计划：一个表名顺序，必须是查询里那几张表的一个排列。"""

    def __init__(self, order):
        self.order = tuple(order)

    def __eq__(self, other):
        return isinstance(other, Plan) and other.order == self.order

    def __hash__(self):
        return hash(self.order)

    def __repr__(self):
        return f"Plan({self.order!r})"


class ExecutionResult:
    """一次执行的结果：选出的行，以及探测过的行数。"""

    def __init__(self, rows, rows_scanned, order):
        self.rows = rows
        self.rows_scanned = rows_scanned
        self.order = order

    def __repr__(self):
        return (
            f"ExecutionResult(rows={len(self.rows)}, "
            f"rows_scanned={self.rows_scanned}, order={self.order!r})"
        )


class Engine:
    """嵌套循环执行器：按计划里的表顺序连，条件随表进入前缀即时生效。"""

    def execute(self, query):
        """按查询声明的表顺序执行。"""
        return self.execute_plan(query, Plan(query.table_names()))

    def execute_plan(self, query, plan):
        """按计划给定的表顺序执行。"""
        order = tuple(plan.order)
        if len(order) != len(set(order)) or set(order) != set(query.table_names()):
            raise ValueError("计划里的表跟查询对不上")
        rows_scanned = 0
        partial = [{}]
        placed = []
        for name in order:
            table = query.table(name)
            table_rows = table.rows()
            conditions = [
                condition
                for condition in query.joins()
                if self._touches(condition, name, placed)
            ]
            extended_partial = []
            for binding in partial:
                for row in table_rows:
                    rows_scanned += 1
                    if self._matches(query, binding, name, row, conditions):
                        extended = dict(binding)
                        extended[name] = row
                        extended_partial.append(extended)
            partial = extended_partial
            placed.append(name)
        return ExecutionResult(self._project(query, partial), rows_scanned, order)

    @staticmethod
    def _touches(condition, name, placed):
        t1, _, t2, _ = condition
        if t1 == name:
            return t2 in placed
        if t2 == name:
            return t1 in placed
        return False

    @staticmethod
    def _matches(query, binding, name, row, conditions):
        for t1, c1, t2, c2 in conditions:
            if t1 == name:
                left, left_col = row, c1
                right, right_col = binding[t2], c2
            else:
                left, left_col = binding[t1], c1
                right, right_col = row, c2
            if (
                left[query.table(t1).column_index(left_col)]
                != right[query.table(t2).column_index(right_col)]
            ):
                return False
        return True

    @staticmethod
    def _project(query, partial):
        select = query.select()
        projected = []
        for binding in partial:
            values = []
            for item in select:
                name, _, column = item.partition(".")
                table = query.table(name)
                values.append(binding[name][table.column_index(column)])
            projected.append(tuple(values))
        return projected
