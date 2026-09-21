"""内存表。

行是值元组，元组的顺序跟 columns 一致，值必须可哈希。
每次写入都会推进 revision，统计快照靠它判断自己是不是过期了。
"""


class Table:
    """一张内存表，按表名在查询里被引用。"""

    def __init__(self, name, columns):
        if not name:
            raise ValueError("表名不能为空")
        self.name = name
        self.columns = tuple(columns)
        if not self.columns:
            raise ValueError(f"表 {name} 至少要有一列")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError(f"表 {name} 的列名有重复")
        self._rows = []
        self.revision = 0

    def insert(self, row):
        """插入一行，返回它的下标。"""
        row = tuple(row)
        if len(row) != len(self.columns):
            raise ValueError(
                f"表 {self.name} 有 {len(self.columns)} 列，收到 {len(row)} 个值"
            )
        self._rows.append(row)
        self.revision += 1
        return len(self._rows) - 1

    def insert_many(self, rows):
        """批量插入，返回各行的下标。"""
        return [self.insert(row) for row in rows]

    def rows(self):
        """按插入顺序返回行，副本。"""
        return list(self._rows)

    def row_count(self):
        """行数。"""
        return len(self._rows)

    def column_index(self, column):
        """列名转下标，列不存在抛 KeyError。"""
        try:
            return self.columns.index(column)
        except ValueError:
            raise KeyError(f"表 {self.name} 没有列 {column}") from None

    def distinct(self, column):
        """列上不同值的个数，扫一遍列再计数，空表算 0。"""
        index = self.column_index(column)
        return len({row[index] for row in self._rows})

    def __repr__(self):
        return f"Table({self.name!r}, columns={self.columns!r}, rows={len(self._rows)})"
