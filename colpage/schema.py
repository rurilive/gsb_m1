"""列定义与行校验。

一张表由若干列组成，每列有名字和类型（int 或 str），行的键就是列名。
文件里存的就是这张表拆开后的各列数据。
"""

from colpage.errors import SchemaError

KINDS = ("int", "str")
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


class Schema:
    """列定义：一串 (列名, 类型) 对，列名不许重复。"""

    def __init__(self, columns):
        self._columns = []
        for item in columns:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise SchemaError("列定义要写成 (列名, 类型): %r" % (item,))
            name, kind = item
            if not isinstance(name, str) or not name:
                raise SchemaError("列名必须是非空字符串: %r" % (name,))
            if kind not in KINDS:
                raise SchemaError("列 %s 的类型 %r 不认识，只支持 %s"
                                  % (name, kind, " / ".join(KINDS)))
            if name in [column[0] for column in self._columns]:
                raise SchemaError("列名重复: %s" % name)
            self._columns.append((name, kind))

    @property
    def columns(self):
        """(列名, 类型) 列表的拷贝。"""
        return list(self._columns)

    @property
    def names(self):
        return [name for name, _ in self._columns]

    def __len__(self):
        return len(self._columns)

    def index(self, name):
        """列名对应的序号，表上没有这一列就抛 SchemaError。"""
        for position, column in enumerate(self._columns):
            if column[0] == name:
                return position
        raise SchemaError("没有这一列: %s" % name)

    def kind(self, name):
        """列名对应的类型。"""
        return self._columns[self.index(name)][1]

    def validate_row(self, row):
        """检查一行能否存进这张表，不合格抛 SchemaError。"""
        if not isinstance(row, dict):
            raise SchemaError("行要写成字典: %r" % (row,))
        for name, kind in self._columns:
            if name not in row:
                raise SchemaError("行里缺列 %s" % name)
            value = row[name]
            if kind == "int":
                if not isinstance(value, int) or isinstance(value, bool):
                    raise SchemaError("列 %s 是 int，收到 %r" % (name, value))
                if not INT64_MIN <= value <= INT64_MAX:
                    raise SchemaError("列 %s 的值超出 64 位有符号整数: %r" % (name, value))
            elif not isinstance(value, str):
                raise SchemaError("列 %s 是 str，收到 %r" % (name, value))
        for key in row:
            if key not in self.names:
                raise SchemaError("行里有表上没有的列: %s" % key)

    def __eq__(self, other):
        return isinstance(other, Schema) and self._columns == other._columns

    def __repr__(self):
        return "Schema(%r)" % (self._columns,)
