"""按权重把一笔总额分摊到若干账户。

分摊全程用整数分运算：权重先按小数位对齐放大成整数，份额用整数
乘除算出，既不丢精度，也不用逐户套 Decimal 高精度运算。
"""

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
    elif isinstance(value, bool):
        raise MoneyError("权重类型不认识: %r" % (value,))
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


def _weights_to_ints(scaled):
    """把一组非负 Decimal 权重按小数位对齐，放大成整数比例。"""
    exponent = min(weight.as_tuple().exponent for weight in scaled)
    if exponent >= 0:
        return [int(weight) for weight in scaled]
    factor = 10 ** (-exponent)
    return [int(weight * factor) for weight in scaled]


def _round_half_away(numerator, denominator):
    """numerator / denominator 四舍五入取整（denominator > 0）。

    与 Decimal 的 ROUND_HALF_UP 一致：半数向远离零的方向进。
    """
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((2 * -numerator + denominator) // (2 * denominator))


def allocate_cents(total_cents, weights):
    """整数分口径的分摊。

    返回 (shares_cents, residual_cents, weight_ints)：逐户份额（整数分，
    与 weights 一一对应）、摊不平的尾差（整数分）、对齐放大后的整数
    权重（给调用方挑尾差归属用）。权重全为零时整笔挂账：各户都是零，
    尾差等于总额。
    """
    if not weights:
        raise ValueError("至少要有一个账户才能分摊")
    weight_ints = _weights_to_ints([as_weight(weight) for weight in weights])
    weight_sum = sum(weight_ints)
    if weight_sum == 0:
        return [0] * len(weight_ints), total_cents, weight_ints
    shares = [
        _round_half_away(total_cents * weight, weight_sum)
        for weight in weight_ints
    ]
    residual = total_cents - sum(shares)
    return shares, residual, weight_ints


def allocate(total, weights):
    """把 total 按各账户权重摊开。

    总额先折到整数分，分摊以分为最小单位，逐户四舍五入到分。权重
    可以带小数，权重全为零时整笔挂账：各户都是零，尾差等于总额，
    不落给任何账户。摊不平的分位尾差记在 Allocation.residual 里，
    交给调用方按财务口径结算。
    """
    if not weights:
        raise ValueError("至少要有一个账户才能分摊")
    amount = as_amount(total)
    total_cents = to_cents(amount)
    shares, residual, _ = allocate_cents(total_cents, weights)
    return Allocation(
        from_cents(total_cents),
        [from_cents(share) for share in shares],
        from_cents(residual),
    )
