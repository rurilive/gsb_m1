"""nttx 的多项式核心：整数系数多项式的朴素（基线）实现。

本模块当前只提供平方级的能力，所有算法都是直白的双重循环或逐点代入，
没有任何变换加速：

    - 乘法用双重循环逐项卷积，两两相乘后按次数累加，复杂度平方级；
    - 求值用逐点代入，对每个横坐标走一遍霍纳方式；
    - 整数除法取模走逐项处理，把每一项系数单独归一。

这些行为是包内其余模块与测试所依赖的现状，必须保持正确且确定。
"""

class NttxError(Exception):
    """本包所有异常的基类，调用方捕获它就能兜住全部失败。"""


class InvalidCoefficientsError(NttxError):
    """系数序列不合法（含非整数项、不是可迭代对象等）。"""


class InvalidModulusError(NttxError):
    """模数不是大于一的整数。"""


class EmptyPolynomialError(NttxError):
    """对零多项式做了不支持的取值或规范化操作。"""


class EvaluationError(NttxError):
    """求值时给定的点与多项式不匹配。"""


def _normalize(coefficients):
    """把系数序列规范化为低位在前、末尾去零的内部表示。"""
    if coefficients is None:
        raise InvalidCoefficientsError("系数不能为 None")
    try:
        seq = list(coefficients)
    except TypeError:
        raise InvalidCoefficientsError("系数必须是可迭代的整数序列")
    for value in seq:
        if not isinstance(value, int) or isinstance(value, bool):
            raise InvalidCoefficientsError(f"系数必须是整数，实际拿到 {value!r}")
    seq = [int(v) for v in seq]
    while seq and seq[-1] == 0:
        seq.pop()
    return seq


class Polynomial:
    """整数系数多项式，低位在前存储（下标即为该项的次数）。

    内部系数始终去掉了高次的零；零多项式用空列表表示，打印为 0。
    """

    def __init__(self, coefficients=None):
        self._coeffs = _normalize(coefficients if coefficients is not None else [])

    @property
    def coefficients(self):
        """返回内部系数列表的副本，低位在前。"""
        return list(self._coeffs)

    def degree(self):
        """返回次数；零多项式返回 -1。"""
        return len(self._coeffs) - 1

    def is_zero(self):
        """是否为零多项式。"""
        return not self._coeffs

    def __eq__(self, other):
        if not isinstance(other, Polynomial):
            return NotImplemented
        return self._coeffs == other._coeffs

    def __hash__(self):
        return hash(tuple(self._coeffs))

    def __repr__(self):
        return f"Polynomial({self._coeffs!r})"

    def __add__(self, other):
        other = self._coerce(other)
        n = max(len(self._coeffs), len(other._coeffs))
        out = [0] * n
        for i in range(n):
            a = self._coeffs[i] if i < len(self._coeffs) else 0
            b = other._coeffs[i] if i < len(other._coeffs) else 0
            out[i] = a + b
        return Polynomial(out)

    def __sub__(self, other):
        other = self._coerce(other)
        n = max(len(self._coeffs), len(other._coeffs))
        out = [0] * n
        for i in range(n):
            a = self._coeffs[i] if i < len(self._coeffs) else 0
            b = other._coeffs[i] if i < len(other._coeffs) else 0
            out[i] = a - b
        return Polynomial(out)

    def __neg__(self):
        return Polynomial([-c for c in self._coeffs])

    def __mul__(self, other):
        """朴素乘法：逐项卷积，平方级。"""
        other = self._coerce(other)
        if self.is_zero() or other.is_zero():
            return Polynomial([])
        a = self._coeffs
        b = other._coeffs
        out = [0] * (len(a) + len(b) - 1)
        for i, av in enumerate(a):
            if av == 0:
                continue
            for j, bv in enumerate(b):
                out[i + j] += av * bv
        return Polynomial(out)

    __rmul__ = __mul__

    def scalar_mul(self, k):
        """整体乘一个整数。"""
        if not isinstance(k, int) or isinstance(k, bool):
            raise InvalidCoefficientsError(f"标量必须是整数，实际拿到 {k!r}")
        return Polynomial([c * k for c in self._coeffs])

    def evaluate(self, x):
        """在单点 x 处求值，用霍纳方式逐项代入。"""
        result = 0
        for c in reversed(self._coeffs):
            result = result * x + c
        return result

    def evaluate_many(self, points):
        """在多个点处求值，逐点调用单点求值。"""
        return [self.evaluate(x) for x in points]

    def scalar_mod(self, m):
        """逐项对 m 取模，把系数归一到零到 m 减一的区间。

        m 必须是大于一的整数；对每一项系数单独处理，负数按 Python 的
        取模语义归一到非负区间。
        """
        if not isinstance(m, int) or isinstance(m, bool) or m <= 1:
            raise InvalidModulusError(f"模数必须是大于一的整数，实际拿到 {m!r}")
        return Polynomial([c % m for c in self._coeffs])

    @classmethod
    def from_roots(cls, roots):
        """用逐项相乘的方式由根构造多项式，用于对照。"""
        result = Polynomial([1])
        for r in roots:
            result = result * Polynomial([-r, 1])
        return result

    def _coerce(self, other):
        if isinstance(other, Polynomial):
            return other
        if isinstance(other, int) and not isinstance(other, bool):
            return Polynomial([other])
        raise InvalidCoefficientsError(f"无法把 {other!r} 当作多项式参与运算")


def convolve(a, b):
    """两个系数序列的朴素卷积，返回低位在前的系数列表。"""
    pa = Polynomial(a)
    pb = Polynomial(b)
    return (pa * pb).coefficients


def deduce_length(a, b):
    """朴素卷积结果的长度，零多项式返回零。"""
    pa = Polynomial(a)
    pb = Polynomial(b)
    if pa.is_zero() or pb.is_zero():
        return 0
    return len(pa.coefficients) + len(pb.coefficients) - 1


def validate_points(poly, points):
    """检查求值点与多项式是否匹配（个数不少于次数加一）。"""
    if not isinstance(poly, Polynomial):
        raise EvaluationError("第一个参数必须是多项式")
    if len(points) < poly.degree() + 1:
        raise EvaluationError("求值点个数少于多项式次数加一")
    if poly.is_zero() and not points:
        raise EmptyPolynomialError("零多项式需要至少一个求值点")
    return True
