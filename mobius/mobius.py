"""mobius 的朴素莫比乌斯反演实现（改造前的现状）。

现在只有一条路径：求莫比乌斯函数时对每个数单独做质因数分解、再逐个判断
有没有重复的质因子；求互素数对个数或最大公约数为某个值的数对个数时用双重
循环逐对枚举、逐对求最大公约数再判定。规模一小结果清楚，规模一大就平方级
地慢下去。一趟线性筛同时筛出质数、莫比乌斯函数与最小质因子，再按倍数贡献
用类似埃氏筛的调和级数方式对多个倍数做前缀累加、把反演求值降到近似线性对
数级，见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class ValueTypeError(Erro):
    """参数类型不合法的输入。"""


class NumberRangeError(Erro):
    """整数的取值范围不合法。"""


def _require_int(value, name):
    """要求 value 是整数（布尔值不算），否则抛 ValueTypeError。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueTypeError("%s must be an int" % (name,))
    return value


class Inversion:
    """给定上界，用逐数枚举这一种方式做莫比乌斯函数与数对计数。"""

    def __init__(self, upper):
        _require_int(upper, "upper")
        if upper < 0:
            raise NumberRangeError("upper must not be negative")
        self._upper = upper
        self._divisions = 0

    def upper(self):
        """返回构造时给定的上界。"""
        return self._upper

    def reset_counts(self):
        """把试除计数清零。"""
        self._divisions = 0

    def trial_divisions(self):
        """自上次清零以来累计试除了多少次（每做一次取余判断算一次）。"""
        return self._divisions

    def _factorize_naive(self, x):
        """朴素分解：从二起反复试除因子，返回升序质因子元组（含重数）。"""
        result = []
        n = x
        if n < 2:
            return tuple(result)
        d = 2
        while d * d <= n:
            while True:
                self._divisions += 1
                if n % d != 0:
                    break
                result.append(d)
                n //= d
            d += 1 if d == 2 else 2
        if n > 1:
            result.append(n)
        return tuple(result)

    def mobius(self, x):
        """返回莫比乌斯函数值：含平方因子取零，否则按质因子个数取正负一。"""
        _require_int(x, "x")
        if x < 1:
            raise NumberRangeError("x must be positive")
        if x == 1:
            return 1
        factors = self._factorize_naive(x)
        for i in range(1, len(factors)):
            if factors[i] == factors[i - 1]:
                return 0
        return -1 if len(factors) % 2 else 1

    def mobius_values(self):
        """返回从一到上界每个数的莫比乌斯函数值，升序元组（逐个判定）。"""
        return tuple(self.mobius(x) for x in range(1, self._upper + 1))

    def gcd(self, a, b):
        """用辗转相除求两个非负整数的最大公约数。"""
        _require_int(a, "a")
        _require_int(b, "b")
        if a < 0 or b < 0:
            raise NumberRangeError("a and b must not be negative")
        while b:
            self._divisions += 1
            a, b = b, a % b
        return a

    def count_coprime_pairs(self, limit):
        """统计不超过上界的互异数对中互素的个数（双重循环逐对判定）。"""
        _require_int(limit, "limit")
        if limit < 0:
            raise NumberRangeError("limit must not be negative")
        total = 0
        for a in range(1, limit + 1):
            for b in range(a + 1, limit + 1):
                if self.gcd(a, b) == 1:
                    total += 1
        return total

    def count_pairs_gcd(self, limit, g):
        """统计一到上界间有序数对中最大公约数恰为 g 的个数（逐对判定）。"""
        _require_int(limit, "limit")
        _require_int(g, "g")
        if limit < 0:
            raise NumberRangeError("limit must not be negative")
        if g < 1:
            raise NumberRangeError("g must be positive")
        total = 0
        for a in range(1, limit + 1):
            for b in range(1, limit + 1):
                if self.gcd(a, b) == g:
                    total += 1
        return total

    def count_coprime_pairs_in(self, values):
        """统计一批整数中互素的下标对的个数（逐对判定），按下标升序不论次序。"""
        if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
            raise ValueTypeError("values must be a sequence of int")
        items = []
        for v in values:
            _require_int(v, "value")
            if v < 1:
                raise NumberRangeError("value must be positive")
            items.append(v)
        total = 0
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if self.gcd(items[i], items[j]) == 1:
                    total += 1
        return total
