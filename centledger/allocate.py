"""按权重把一笔总额分摊到若干账户。"""

from decimal import Decimal

from .money import MoneyError, ZERO, from_cents, to_cents


class Allocation(object):
    """一笔分摊的结果。

    total     本次分摊的总额（Decimal）
    shares    各账户分到的金额，与权重一一对应（list[Decimal]）
    residual  逐户舍入到分之后剩下的尾差（Decimal）
    """

    def __init__(self, total, shares, residual):
        self.total = total
        self.shares = list(shares)
        self.residual = residual

    def total_allocated(self):
        return sum(self.shares, ZERO)

    def __repr__(self):
        return "Allocation(total=%s, allocated=%s, residual=%s)" % (
            self.total, self.total_allocated(), self.residual)


def as_amount(value):
    """把金额字段（str / int / Decimal）解析成 Decimal。"""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise MoneyError("金额必须是有限值: %r" % (value,))
        return value
    if isinstance(value, (int, str)):
        try:
            parsed = Decimal(str(value))
        except ArithmeticError as exc:
            raise MoneyError("金额解析不了: %r" % (value,)) from exc
        if not parsed.is_finite():
            raise MoneyError("金额必须是有限值: %r" % (value,))
        return parsed
    raise MoneyError("金额类型不认识: %r" % (value,))


def as_weight(value):
    """把权重字段解析成非负 Decimal。"""
    if isinstance(value, Decimal):
        weight = value
    elif isinstance(value, int):
        weight = Decimal(value)
    elif isinstance(value, str):
        try:
            weight = Decimal(value)
        except ArithmeticError as exc:
            raise MoneyError("权重解析不了: %r" % (value,)) from exc
    else:
        raise MoneyError("权重类型不认识: %r" % (value,))
    if not weight.is_finite():
        raise MoneyError("权重必须是有限值: %r" % (value,))
    if weight < 0:
        raise MoneyError("权重不能为负: %r" % (value,))
    return weight


def _round_half_up_div(numerator, denominator):
    """整数除法四舍五入（平局远离零），denominator 必须为正整数。"""
    quotient, remainder = divmod(abs(numerator), denominator)
    if remainder * 2 >= denominator:
        quotient += 1
    return quotient if numerator >= 0 else -quotient


def _scale_weight(weight, shift):
    """把 Decimal 权重精确放大 10**shift 倍成整数，不经过浮点。"""
    digits = weight.as_tuple().digits
    value = 0
    for digit in digits:
        value = value * 10 + digit
    exponent = weight.as_tuple().exponent + shift
    if exponent:
        value *= 10 ** exponent
    return value


def allocate(total, weights):
    """把 total 按各账户权重摊开。

    分摊以分为最小单位：总额先折成整数分，权重按小数位统一放大成
    整数，逐户用整数四舍五入（平局远离零）到分，不经过浮点，金额
    再大也不丢精度。权重可以带小数；权重全为零时整笔挂账：各户都
    是零，尾差等于总额，不落给任何账户。摊不平的分位尾差记在
    Allocation.residual 里，交给调用方按财务口径结算。
    """
    if not weights:
        raise ValueError("至少要有一个账户才能分摊")
    amount = as_amount(total)
    parsed = [as_weight(weight) for weight in weights]
    shift = 0
    for weight in parsed:
        exponent = weight.as_tuple().exponent
        if exponent < 0:
            shift = max(shift, -exponent)
    scaled = [_scale_weight(weight, shift) for weight in parsed]
    weight_sum = sum(scaled)
    if weight_sum == 0:
        return Allocation(amount, [ZERO for _ in scaled], amount)
    total_cents = to_cents(amount)
    shares = []
    allocated = 0
    for weight in scaled:
        cents = _round_half_up_div(total_cents * weight, weight_sum)
        allocated += cents
        shares.append(from_cents(cents))
    return Allocation(amount, shares, amount - from_cents(allocated))
