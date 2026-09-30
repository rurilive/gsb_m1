"""差分组件的改造前基线实现。

这里的一切都用最直白的循环与切片完成：区间加就是逐元素改写，
区间求和就是现场重扫整段，二维加就是二重循环。功能正确但规模一大就慢，
也没有任何可观测的改动点计数。
"""


class DiffError(Exception):
    """本模块全部异常的基类。"""


class InvalidSizeError(DiffError):
    """数组规模不合法，例如负数。"""


class InvalidIndexError(DiffError):
    """位置或下标不合法，例如越界。"""


class InvalidRangeError(DiffError):
    """区间不合法，例如左端大于右端，或越界。"""


class InvalidMatrixError(DiffError):
    """二维输入不合法，例如空矩阵或行列不齐。"""


class InvalidShapesError(DiffError):
    """两组形状不一致，无法成对运算。"""


def _as_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidIndexError("位置必须是整数")
    return value


def _is_number(value):
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _check_matrix(matrix):
    if not isinstance(matrix, (list, tuple)) or len(matrix) == 0:
        raise InvalidMatrixError("矩阵必须是非空的二维序列")
    rows = len(matrix)
    cols = None
    for row in matrix:
        if not isinstance(row, (list, tuple)):
            raise InvalidMatrixError("矩阵的每一行都必须是序列")
        if cols is None:
            cols = len(row)
        elif len(row) != cols:
            raise InvalidMatrixError("矩阵各行列数必须一致")
        for value in row:
            if not _is_number(value):
                raise InvalidMatrixError("矩阵元素必须是数字且不能是布尔")
    if cols == 0:
        raise InvalidMatrixError("矩阵的列数必须大于零")
    return rows, cols


def _new_matrix(rows, cols):
    return [[0 for _ in range(cols)] for _ in range(rows)]


class DiffArray:
    """朴素数组，每次区间修改都逐元素改写。"""

    def __init__(self, values):
        try:
            self._data = list(values)
        except TypeError:
            raise InvalidSizeError("初始值必须是可迭代的序列")
        for value in self._data:
            if not _is_number(value):
                raise InvalidSizeError("元素必须是数字且不能是布尔")
        self._changes = 0

    @classmethod
    def zeros(cls, size):
        if isinstance(size, bool) or not isinstance(size, int):
            raise InvalidSizeError("规模必须是整数")
        if size < 0:
            raise InvalidSizeError("规模不能为负数")
        return cls([0] * size)

    def size(self):
        return len(self._data)

    def __len__(self):
        return len(self._data)

    def value_at(self, index):
        index = _as_int(index)
        if index < 0 or index >= len(self._data):
            raise InvalidIndexError("下标越界: " + str(index))
        return self._data[index]

    def range_add(self, left, right, delta):
        left = _as_int(left)
        right = _as_int(right)
        if not _is_number(delta):
            raise InvalidRangeError("增量必须是数字且不能是布尔")
        if left > right:
            raise InvalidRangeError("左端不能大于右端")
        if left < 0 or right >= len(self._data):
            raise InvalidRangeError("区间越界: " + str(left) + " " + str(right))
        for i in range(left, right + 1):
            self._data[i] = self._data[i] + delta
            self._changes += 1

    def prefix_sum(self, index):
        index = _as_int(index)
        if index < 0 or index >= len(self._data):
            raise InvalidIndexError("下标越界: " + str(index))
        total = 0
        for i in range(0, index + 1):
            total += self._data[i]
            self._changes += 1
        return total

    def range_sum(self, left, right):
        left = _as_int(left)
        right = _as_int(right)
        if left > right:
            raise InvalidRangeError("左端不能大于右端")
        if left < 0 or right >= len(self._data):
            raise InvalidRangeError("区间越界: " + str(left) + " " + str(right))
        total = 0
        for i in range(left, right + 1):
            total += self._data[i]
            self._changes += 1
        return total

    def total_sum(self):
        return self.range_sum(0, len(self._data) - 1)

    def to_list(self):
        return list(self._data)

    def replay(self, operations):
        """按离线操作序列逐条执行区间加，最后返回整数组。"""
        self._changes = 0
        for operation in operations:
            left, right, delta = operation
            self.range_add(left, right, delta)
        return self.to_list()

    def change_count(self):
        return self._changes

    def reset_change_count(self):
        self._changes = 0


class DiffMatrix:
    """朴素二维数组，每次区域加都逐格改写。"""

    def __init__(self, rows):
        self._rows, self._cols = _check_matrix(rows)
        self._data = [list(row) for row in rows]
        self._changes = 0

    @classmethod
    def zeros(cls, rows, cols):
        if isinstance(rows, bool) or not isinstance(rows, int):
            raise InvalidSizeError("行数必须是整数")
        if isinstance(cols, bool) or not isinstance(cols, int):
            raise InvalidSizeError("列数必须是整数")
        if rows <= 0 or cols <= 0:
            raise InvalidSizeError("行列数都必须大于零")
        return cls(_new_matrix(rows, cols))

    def shape(self):
        return (self._rows, self._cols)

    def value_at(self, row, col):
        row = _as_int(row)
        col = _as_int(col)
        if row < 0 or row >= self._rows or col < 0 or col >= self._cols:
            raise InvalidIndexError("下标越界: " + str(row) + " " + str(col))
        return self._data[row][col]

    def region_add(self, row1, col1, row2, col2, delta):
        row1 = _as_int(row1)
        col1 = _as_int(col1)
        row2 = _as_int(row2)
        col2 = _as_int(col2)
        if not _is_number(delta):
            raise InvalidRangeError("增量必须是数字且不能是布尔")
        if row1 > row2 or col1 > col2:
            raise InvalidRangeError("左上角不能大于右下角")
        if row1 < 0 or col1 < 0 or row2 >= self._rows or col2 >= self._cols:
            raise InvalidRangeError(
                "区域越界: " + str(row1) + " " + str(col1) + " "
                + str(row2) + " " + str(col2))
        for r in range(row1, row2 + 1):
            for c in range(col1, col2 + 1):
                self._data[r][c] = self._data[r][c] + delta
                self._changes += 1

    def values(self):
        return [list(row) for row in self._data]

    def change_count(self):
        return self._changes

    def reset_change_count(self):
        self._changes = 0


def flatten(matrix):
    return [value for row in matrix for value in row]


def elementwise_add(a, b):
    """两组逐项相加，形状必须一致。"""
    if isinstance(a, DiffMatrix) and isinstance(b, DiffMatrix):
        if a.shape() != b.shape():
            raise InvalidShapesError("两组形状不一致")
        rows = _new_matrix(a.shape()[0], a.shape()[1])
        for r in range(a.shape()[0]):
            for c in range(a.shape()[1]):
                rows[r][c] = a.value_at(r, c) + b.value_at(r, c)
        return rows
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            raise InvalidShapesError("两组形状不一致")
        return [x + y for x, y in zip(a, b)]
    raise InvalidShapesError("两组形状不一致")


def elementwise_equal(a, b):
    """两组逐项相等判定，形状必须一致。"""
    if isinstance(a, DiffMatrix) and isinstance(b, DiffMatrix):
        if a.shape() != b.shape():
            raise InvalidShapesError("两组形状不一致")
        for r in range(a.shape()[0]):
            for c in range(a.shape()[1]):
                if a.value_at(r, c) != b.value_at(r, c):
                    return False
        return True
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            raise InvalidShapesError("两组形状不一致")
        for x, y in zip(a, b):
            if x != y:
                return False
        return True
    raise InvalidShapesError("两组形状不一致")
