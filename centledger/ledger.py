"""多账户账本：按批接收分摊请求，维护余额并提供对账。"""

from .allocate import allocate, as_amount, as_weight
from .money import ZERO, MoneyError, format_cents, from_cents, to_cents


class BatchRequest(object):
    """一批里的一笔请求。

    total   本次要摊出去的总额（str / int / Decimal）
    weights 账户到权重的映射，权重非负，可以带小数
    """

    def __init__(self, total, weights):
        self.total = as_amount(total)
        self.weights = dict(weights)

    @property
    def accounts(self):
        return list(self.weights)

    def __repr__(self):
        return "BatchRequest(total=%r, weights=%r)" % (self.total, self.weights)


class BatchResult(object):
    """一批请求记完账之后的结果。

    batch_id 批次号
    credits  账户到本批给它的分摊合计
    balances 账户到记完这批之后的余额
    """

    def __init__(self, batch_id, credits, balances):
        self.batch_id = batch_id
        self.credits = dict(credits)
        self.balances = dict(balances)

    def render(self):
        """批次结果的文本表示，对账系统按文本逐字节比对。"""
        lines = ["batch %s" % self.batch_id]
        for account in sorted(self.credits):
            credit = self.credits[account]
            lines.append("%s credit=%s balance=%s" % (
                account,
                format_cents(to_cents(credit)),
                format_cents(to_cents(self.balances[account])),
            ))
        return "\n".join(lines) + "\n"

    def __repr__(self):
        return "BatchResult(batch_id=%r, accounts=%d)" % (
            self.batch_id, len(self.credits))


class ReconcileReport(object):
    """对账结果。

    requests   处理过的请求笔数
    total_in   请求总额合计
    total_out  各账户余额合计
    difference total_out 与 total_in 的差额
    """

    def __init__(self, requests, total_in, total_out):
        self.requests = requests
        self.total_in = total_in
        self.total_out = total_out
        self.difference = total_out - total_in

    @property
    def ok(self):
        return self.difference == 0

    def render(self):
        return "requests=%d in=%s out=%s diff=%s" % (
            self.requests,
            format_cents(to_cents(self.total_in)),
            format_cents(to_cents(self.total_out)),
            format_cents(to_cents(self.difference)),
        )


class Ledger(object):
    """按批记账的账户集合。"""

    def __init__(self):
        self._balances = {}
        self._total_in = ZERO
        self._requests = 0
        self._batches = {}

    def balance(self, account):
        """单个账户当前的余额。"""
        return self._balances.get(account, ZERO)

    def balances(self):
        """全部账户余额的副本。"""
        return dict(self._balances)

    def apply_batch(self, batch_id, requests):
        """把一批请求记进账本，返回 BatchResult。

        同一批次号重放同一批请求时，直接返回首次记账的结果，余额和
        对账统计不重复累计；批次号相同但内容对不上时报 ValueError。
        一批里有任何一笔不合法，整批都不入账。
        """
        requests = list(requests)
        if batch_id in self._batches:
            stored_requests, stored_result = self._batches[batch_id]
            if not _same_requests(stored_requests, requests):
                raise ValueError("批次号 %r 已经记过账，重放内容对不上" % (batch_id,))
            return stored_result
        credits = {}
        total_in = 0
        for request in requests:
            total_in += self._post(request, credits)
        balances = {}
        for account, credit in credits.items():
            balance = self._balances.get(account, ZERO) + credit
            self._balances[account] = balance
            balances[account] = balance
        self._total_in += from_cents(total_in)
        self._requests += len(requests)
        result = BatchResult(batch_id, credits, balances)
        self._batches[batch_id] = (requests, result)
        return result

    def reconcile(self):
        """把请求总额和账户余额合起来对一遍。"""
        total_out = sum(self._balances.values(), ZERO)
        return ReconcileReport(self._requests, self._total_in, total_out)

    def _post(self, request, credits):
        """记一笔请求到 credits，返回入账总额（整数分）。

        不合法时抛错，抛错前不动账本和 credits 以外的任何状态。
        """
        weights = request.weights
        if not weights:
            raise ValueError("请求里没有账户")
        total_cents = to_cents(request.total)
        if total_cents == 0:
            if request.total != 0:
                raise MoneyError("金额不足一分，记不了账: %r" % (request.total,))
            return 0
        parsed = _normalized_weights(weights)
        allocation = allocate(from_cents(total_cents), list(parsed.values()))
        for account, share in zip(weights, allocation.shares):
            credits[account] = credits.get(account, ZERO) + share
        residual = allocation.residual
        if residual:
            target = _residual_target(parsed)
            if target is not None:
                credits[target] = credits.get(target, ZERO) + residual
        return total_cents


def _normalized_weights(weights):
    """账户到 Decimal 权重的映射，用于比较和挑选尾差归宿。"""
    return {name: as_weight(weight) for name, weight in weights.items()}


def _same_requests(first, second):
    """两批请求是否内容一致（总额、账户、权重都相同）。"""
    if len(first) != len(second):
        return False
    for old, new in zip(first, second):
        if old.total != new.total:
            return False
        if _normalized_weights(old.weights) != _normalized_weights(new.weights):
            return False
    return True


def _residual_target(parsed_weights):
    """尾差归宿：权重最大的账户，并列取账户名排序靠前的。

    权重全为零时整笔挂账，不落给任何账户，返回 None。
    """
    top = max(parsed_weights.values())
    if top == 0:
        return None
    return min(name for name, weight in parsed_weights.items() if weight == top)
