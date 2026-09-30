"""朴素计数工具包（改造前基线）。

现有能力都靠逐个数枚举判定完成：

- count_not_divisible(limit, primes)：从一到上界逐个取数，对每个数再逐个素数
  试除，统计没有任何一个素数整除它的数的个数。
- count_coprime_in_range(low, high, numbers)：对区间里的每个整数，逐个与给定
  的一组数求最大公约数，统计与这组数全部互素的数的个数。
- count_union(sets)：把若干个集合合并成一个大集合，再数它的大小。
- count_multi_condition(limit, conditions)：逐个取数，对每个数再逐条检查条件，
  统计满足全部条件的数的个数。

规模一大就慢：判断次数与上界成线性，每次判断还要对素数集合再走一遍，
于是总代价近似上界乘以素数个数。纯标准库，无外部依赖，不引入第三方。
"""

from math import gcd


class CountingError(ValueError):
    """本模块参数与取值范围错误的基类。"""


def _check_limit(limit):
    """上界必须是非负整数，否则抛 CountingError。"""
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise CountingError("limit must be a non-negative integer")
    if limit < 0:
        raise CountingError("limit must be a non-negative integer")
    return limit


def _check_numbers(numbers):
    """一组除数必须是正整数的序列，逐个校验后返回元组。"""
    try:
        items = tuple(numbers)
    except TypeError:
        raise CountingError("numbers must be a sequence of positive integers")
    for n in items:
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise CountingError("numbers must be positive integers")
    return items


def _is_prime(n):
    """试除法判断 n 是否为素数。"""
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


def _check_primes(primes):
    """素数集合里的每个元素都必须是素数，否则抛 CountingError。"""
    items = _check_numbers(primes)
    for n in items:
        if not _is_prime(n):
            raise CountingError("every prime must be a prime number")
    return items


class Counting:
    """逐个枚举判定的朴素计数工具。

    每个方法都先枚举候选整数，再对其逐个判定，接口只读，不保留跨调用状态。
    """

    def count_not_divisible(self, limit, primes):
        """求不超过 limit 且不能被 primes 中任意一个整除的数的个数。

        从一到 limit 逐个取数，每个数再逐个素数试除，一旦能整除就排除。
        limit 为 0 时返回 0。
        """
        limit = _check_limit(limit)
        primes = _check_primes(primes)
        n = 0
        for value in range(1, limit + 1):
            if not any(value % p == 0 for p in primes):
                n += 1
        return n

    def count_coprime_in_range(self, low, high, numbers):
        """求闭区间 low 到 high 内与 numbers 全部互素的数的个数。

        high 小于 low 时返回 0。与一组数互素，指与它们每一个的最大公约数都为 1。
        """
        low = _check_limit(low)
        high = _check_limit(high)
        numbers = _check_numbers(numbers)
        if high < low:
            return 0
        n = 0
        for value in range(low, high + 1):
            if all(gcd(value, k) == 1 for k in numbers):
                n += 1
        return n

    def count_union(self, sets):
        """求若干个集合的并集大小，逐个元素合并去重后计数。"""
        merged = set()
        for one in sets:
            for item in one:
                merged.add(item)
        return len(merged)

    def count_multi_condition(self, limit, conditions):
        """求不超过 limit 且满足全部 conditions 的数的个数。

        conditions 是若干个一元谓词，逐个取数后对每个数逐条判定。
        """
        limit = _check_limit(limit)
        conditions = tuple(conditions)
        n = 0
        for value in range(1, limit + 1):
            if all(pred(value) for pred in conditions):
                n += 1
        return n
