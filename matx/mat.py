"""matx.mat：朴素整数矩阵工具（改造前基线）。

用二维列表表示方阵，全部运算走最直白的循环：

  mat_mul(a, b)      三重循环逐项乘加求乘积（立方级）
  mat_power(a, n)    连续自乘 n 次求幂（线性次乘法）
  mat_add(a, b)      逐项相加
  mat_zeros(n)       零矩阵
  mat_identity(n)    单位矩阵
  mat_diagonal(v)    对角矩阵
  fib(n)             连续迭代求第 n 个斐波那契数

这些做法直观可靠，但都只求正确、不问代价：矩阵幂需要 n 次乘法，
斐波那契需要 n 次加法，指数或下标一大就明显吃力，也拿不出任何
把乘加次数量出来的手段。
"""

__all__ = [
    "MatError",
    "ShapeError",
    "IndexError",
    "InvalidModuloError",
    "NaiveMat",
    "mat_zeros",
    "mat_identity",
    "mat_diagonal",
    "mat_mul",
    "mat_add",
    "mat_power",
    "fib",
]


class MatError(Exception):
    """matx 所有异常的基类。"""


class ShapeError(MatError):
    """矩阵维度不匹配或不是方阵。"""


class IndexError(MatError):
    """幂指数非法（负数）。"""


class InvalidModuloError(MatError):
    """模数非法（零或负数）。"""


def _check_square(a, name="a"):
    if not isinstance(a, list):
        raise ShapeError("矩阵必须是二维列表：%s" % name)
    n = len(a)
    for row in a:
        if not isinstance(row, list) or len(row) != n:
            raise ShapeError("矩阵必须是方阵：%s" % name)
    return n


def _validate_mod(m):
    if m is None:
        return None
    if not isinstance(m, int) or isinstance(m, bool):
        raise InvalidModuloError("模数必须是整数")
    if m <= 0:
        raise InvalidModuloError("模数必须为正整数，当前为 %r" % (m,))
    return m


def mat_zeros(n):
    """返回 n 阶零矩阵。"""
    return [[0] * n for _ in range(n)]


def mat_identity(n):
    """返回 n 阶单位矩阵。"""
    rows = mat_zeros(n)
    for i in range(n):
        rows[i][i] = 1
    return rows


def mat_diagonal(values):
    """由对角线元素构造方阵，非对角元素为零。"""
    values = list(values)
    n = len(values)
    rows = mat_zeros(n)
    for i in range(n):
        rows[i][i] = values[i]
    return rows


def _shape_of(a):
    if not isinstance(a, list) or not a:
        raise ShapeError("矩阵必须是非空的二维列表")
    rows = len(a)
    cols = len(a[0])
    for row in a:
        if not isinstance(row, list) or len(row) != cols:
            raise ShapeError("矩阵各行长度必须一致")
    return rows, cols


def mat_add(a, b):
    """逐项相加，要求维度相同。"""
    ra, ca = _shape_of(a)
    rb, cb = _shape_of(b)
    if (ra, ca) != (rb, cb):
        raise ShapeError("相加要求维度相同：(%d,%d) 与 (%d,%d)" % (ra, ca, rb, cb))
    return [[a[i][j] + b[i][j] for j in range(ca)] for i in range(ra)]


def mat_mul(a, b, mod=None):
    """三重循环逐项乘加求乘积，逐项与朴素口径一致。"""
    mod = _validate_mod(mod)
    _, ca = _shape_of(a)
    rb, cb = _shape_of(b)
    if ca != rb:
        raise ShapeError("相乘要求内维一致：%d 与 %d" % (ca, rb))
    out = [[0] * cb for _ in range(len(a))]
    for i in range(len(a)):
        for j in range(cb):
            acc = 0
            for k in range(ca):
                acc += a[i][k] * b[k][j]
            if mod is not None:
                acc %= mod
            out[i][j] = acc
    return out


def mat_power(a, n, mod=None):
    """连续自乘 n 次求幂：n 次矩阵乘法，代价随指数线性增长。"""
    mod = _validate_mod(mod)
    _check_square(a)
    if not isinstance(n, int) or isinstance(n, bool):
        raise IndexError("指数必须是整数")
    if n < 0:
        raise IndexError("指数不允许为负：%r" % (n,))
    size = len(a)
    result = mat_identity(size)
    for _ in range(n):
        result = mat_mul(result, a, mod)
    return result


def fib(n, mod=None):
    """连续迭代求第 n 个斐波那契数：fib(0)=0，fib(1)=1，代价随 n 线性增长。"""
    mod = _validate_mod(mod)
    if not isinstance(n, int) or isinstance(n, bool):
        raise IndexError("下标必须是整数")
    if n < 0:
        raise IndexError("下标不允许为负：%r" % (n,))
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
        if mod is not None:
            a %= mod
            b %= mod
    if mod is not None:
        a %= mod
    return a


class NaiveMat:
    """朴素整数方阵：二维列表存储，运算全部走最直白的循环。"""

    def __init__(self, rows):
        n = _check_square(rows)
        self.rows = [list(r) for r in rows]
        self.size = n

    def to_list(self):
        return [list(r) for r in self.rows]

    def mul(self, other, mod=None):
        return NaiveMat(mat_mul(self.rows, other.to_list(), mod))

    def power(self, n, mod=None):
        return NaiveMat(mat_power(self.rows, n, mod))

    def add(self, other):
        return NaiveMat(mat_add(self.rows, other.to_list()))

    def identity(self):
        return NaiveMat(mat_identity(self.size))

    def __eq__(self, other):
        return isinstance(other, NaiveMat) and self.rows == other.rows

    def __repr__(self):
        return "NaiveMat(%r)" % (self.rows,)
