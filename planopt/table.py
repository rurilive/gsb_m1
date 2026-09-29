"""内存行式表的简单容器。

现有能力：一张具名表按谓词逐行判断真假，挑出满足条件的行返回一张新表。
谓词收一个行字典返回真假。逻辑计划、重写与代价估计尚未提供。
"""


class Table:
    """具名行式表。

    name 是表名，rows 是若干行字典，columns 缺省时按行里键首次出现的顺序推导。
    表在构造时把行与列都拷一份，之后对外只读，互不影响调用方手里的数据。
    """

    def __init__(self, name, rows, columns=None):
        if not isinstance(name, str) or not name:
            raise ValueError("table name must be a non-empty string")
        copied = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("each row must be a dict")
            copied.append(dict(row))
        self._name = name
        self._rows = copied
        if columns is None:
            discovered = []
            for row in self._rows:
                for key in row:
                    if key not in discovered:
                        discovered.append(key)
            columns = discovered
        self._columns = tuple(columns)

    @property
    def name(self):
        return self._name

    @property
    def columns(self):
        return self._columns

    def __len__(self):
        return len(self._rows)

    def __iter__(self):
        for row in self._rows:
            yield dict(row)

    def filter(self, predicate):
        """按谓词挑出满足条件的行，返回一张新表，原表不动。"""
        if not callable(predicate):
            raise ValueError("predicate must be callable")
        kept = []
        for row in self._rows:
            if predicate(dict(row)):
                kept.append(dict(row))
        return Table(self._name, kept, self._columns)

    def count(self):
        return len(self._rows)

    def to_dicts(self):
        return [dict(row) for row in self._rows]

    def __repr__(self):
        return "Table(name=%s, rows=%d, columns=%s)" % (
            self._name,
            len(self._rows),
            self._columns,
        )
