"""整数分参考实现：与 centledger 的生产实现相互独立，用来对拍。

生产代码把权重放大成整数后走纯整数路线；这里故意用 Fraction 走
精确有理数路线。两条路算出同样的整数分份额，才有把握说实现没歪。
"""

from fractions import Fraction


def round_half_up_cents(value):
    """把 Fraction 表示的金额四舍五入成整数分（平局远离零）。"""
    quotient, remainder = divmod(abs(value.numerator), value.denominator)
    if remainder * 2 >= value.denominator:
        quotient += 1
    return quotient if value.numerator >= 0 else -quotient


def reference_shares(total_cents, weights):
    """按权重摊 total_cents（整数分），返回每户整数分份额。

    weights 是 Fraction 列表；权重全为零时整笔挂账，返回 None。
    """
    weight_sum = sum(weights, Fraction(0))
    if weight_sum == 0:
        return None
    return [round_half_up_cents(Fraction(total_cents) * weight / weight_sum)
            for weight in weights]


def residual_target(names, weights):
    """尾差归宿：权重最大的账户，并列取账户名排序靠前的。

    权重全为零时整笔挂账，不落给任何账户，返回 None。
    """
    top = max(weights)
    if top == 0:
        return None
    return min(name for name, weight in zip(names, weights) if weight == top)
