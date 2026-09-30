"""数论求和的朴素实现。

主题是整除分块与约数计数，这里先把最直白的现状摆出来：某数论函数的区间前缀和、
各数约数个数之和、不超过某上界与某数互素数的个数之和、按整除商的跳跃求和，全
都靠逐个枚举。上界一大，线性甚至平方量级就把时间压垮。

所有计数一律返回非负整数，区间求和返回整数。这个模块不做缓存，也不留任何跨
次调用的模块级状态，同一输入重复跑结果必然一致。
"""


class GcdSumError(Exception):
    """divblock 内所有可诊断错误的基类。"""

    def __init__(self, message, position=None, data=None):
        super().__init__(message)
        self.message = message
        self.position = position
        self.data = data

    def __str__(self):
        return self.message


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_nonneg(value, name):
    if not _is_int(value):
        raise GcdSumError("参数 " + name + " 必须是整数", position=name, data=value)
    if value < 0:
        raise GcdSumError("参数 " + name + " 不能为负", position=name, data=value)


def gcd(a, b):
    """两数最大公约数，用最朴素的辗转相除。"""
    a = abs(int(a))
    b = abs(int(b))
    if a == 0:
        return b
    if b == 0:
        return a
    while b:
        a, b = b, a % b
    return a


def totient_sieve(n):
    """朴素欧拉函数表，phi[1..n]，逐个筛。"""
    _check_nonneg(n, "n")
    phi = list(range(n + 1))
    for p in range(2, n + 1):
        if phi[p] == p:
            for multiple in range(p, n + 1, p):
                phi[multiple] -= phi[multiple] // p
    if n >= 1:
        phi[1] = 1
    return phi


def mobius_sieve(n):
    """朴素莫比乌斯函数表，mu[1..n]。"""
    _check_nonneg(n, "n")
    mu = [1] * (n + 1)
    is_prime = [True] * (n + 1)
    for p in range(2, n + 1):
        if is_prime[p]:
            for multiple in range(p, n + 1, p):
                is_prime[multiple] = False
                mu[multiple] *= -1
            square = p * p
            for multiple in range(square, n + 1, square):
                mu[multiple] = 0
    if n >= 0:
        mu[0] = 0
    return mu


def _prefix(table, lo, hi):
    total = 0
    i = lo
    while i <= hi:
        total += table[i]
        i += 1
    return total


def totient_prefix_upto(n):
    """不超过 n 的全部数上欧拉函数值之和，逐个累加。"""
    _check_nonneg(n, "n")
    return _prefix(totient_sieve(n), 1, n)


def mobius_prefix_upto(n):
    """不超过 n 的全部数上莫比乌斯函数值之和，逐个累加。"""
    _check_nonneg(n, "n")
    return _prefix(mobius_sieve(n), 1, n)


def range_totient_sum(lo, hi):
    """欧拉函数在闭区间上的区间和，端点退化或反序给零，逐个累加。"""
    _check_nonneg(lo, "lo")
    _check_nonneg(hi, "hi")
    if lo > hi:
        return 0
    if lo == 0:
        lo = 1
    return _prefix(totient_sieve(hi), lo, hi)


def range_mobius_sum(lo, hi):
    """莫比乌斯函数在闭区间上的区间和，端点退化或反序给零，逐个累加。"""
    _check_nonneg(lo, "lo")
    _check_nonneg(hi, "hi")
    if lo > hi:
        return 0
    if lo == 0:
        lo = 1
    return _prefix(mobius_sieve(hi), lo, hi)


def divisor_count_upto(n):
    """各数约数个数之和，外层枚举每个数，内层枚举它的每个因数。"""
    _check_nonneg(n, "n")
    total = 0
    d = 1
    while d <= n:
        total += n // d
        d += 1
    return total


def coprime_count_upto(n, k):
    """不超过 n 的全部数里与 k 互素的个数之和，逐个比对最大公约数。"""
    _check_nonneg(n, "n")
    _check_nonneg(k, "k")
    total = 0
    i = 1
    while i <= n:
        if gcd(i, k) == 1:
            total += 1
        i += 1
    return total


def best_divisor_number_count(n):
    """不超过 n 的数里约数个数最多者对应的约数个数，逐个重数因数。"""
    _check_nonneg(n, "n")
    best = 0
    i = 1
    while i <= n:
        d = 1
        c = 0
        while d <= i:
            if i % d == 0:
                c += 1
            d += 1
        if c > best:
            best = c
        i += 1
    return best


def best_divisor_number_upto(n):
    """不超过 n 的数里约数个数最多且取值最小的那个数，逐个枚举。"""
    _check_nonneg(n, "n")
    if n == 0:
        return 0
    best = 0
    answer = 0
    i = 1
    while i <= n:
        d = 1
        c = 0
        while d <= i:
            if i % d == 0:
                c += 1
            d += 1
        if c > best:
            best = c
            answer = i
        i += 1
    return answer


def naive_scan_count(n):
    """某个求和用逐个枚举时走过的项数，这里是上界加一。"""
    _check_nonneg(n, "n")
    return n + 1


def naive_pair_count(n):
    """某个求和用逐个配对时走过的对数，这里是（上界加一）的平方。"""
    _check_nonneg(n, "n")
    return (n + 1) * (n + 1)
