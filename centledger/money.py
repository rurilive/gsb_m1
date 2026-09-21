"""金额与最小货币单位（分）之间的换算。

账本以整数分记账，金额在进出账本的边界上都要经过这里换算。
"""

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class MoneyError(ValueError):
    """金额没法表示成分。"""


def to_cents(amount):
    """把金额换算成整数分，四舍五入到分。

    amount 可以是 int、str、Decimal 或 float，返回 int。
    """
    try:
        value = Decimal(str(float(amount)))
    except (TypeError, ValueError) as exc:
        raise MoneyError("金额换算不了: %r" % (amount,)) from exc
    if not value.is_finite():
        raise MoneyError("金额必须是有限值: %r" % (amount,))
    return int(value.quantize(CENT, rounding=ROUND_HALF_UP) * 100)


def from_cents(cents):
    """整数分换算回金额（Decimal，两位小数）。"""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise MoneyError("分必须是整数: %r" % (cents,))
    return Decimal(cents).scaleb(-2)


def format_cents(cents):
    """整数分格式化成定点字符串，例如 -1234 变成 -12.34。"""
    sign = "-" if cents < 0 else ""
    value = abs(int(cents))
    return "%s%d.%02d" % (sign, value // 100, value % 100)
