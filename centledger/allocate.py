"""按权重把一笔总额分摊到若干账户。"""

from decimal import Decimal, ROUND_HALF_UP

from .money import CENT, MoneyError, ZERO


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
    elif isinstance(value, (int, str)):
        try:
            weight = Decimal(str(value))
        except ArithmeticError as exc:
            raise MoneyError("权重解析不了: %r" % (value,)) from exc
    else:
        raise MoneyError("权重类型不认识: %r" % (value,))
    if not weight.is_finite():
        raise MoneyError("权重必须是有限值: %r" % (value,))
    if weight < 0:
        raise MoneyError("权重不能为负: %r" % (value,))
    return weight


def allocate(total, weights):
    """把 total 按各账户权重摊开。

    分摊以分为最小单位，逐户四舍五入到分。权重可以带小数，
    权重全为零时整笔挂账：各户都是零，尾差等于总额，不落给任何
    账户。摊不平的分位尾差记在 Allocation.residual 里，交给调用方
    按财务口径结算。
    """
    if not weights:
        raise ValueError("至少要有一个账户才能分摊")
    amount = as_amount(total)
    scaled = [as_weight(weight) for weight in weights]
    weight_sum = sum(scaled, Decimal(0))
    if weight_sum == 0:
        return Allocation(amount, [ZERO for _ in scaled], amount)
    shares = []
    for weight in scaled:
        ratio = weight / weight_sum
        share = (amount * ratio).quantize(CENT, rounding=ROUND_HALF_UP)
        shares.append(share)
    return Allocation(amount, shares, amount - sum(shares, ZERO))
