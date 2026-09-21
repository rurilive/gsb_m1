"""多账户账本：按批接收分摊请求，维护余额并提供对账。"""

from .allocate import allocate, as_amount, as_weight
from .money import ZERO, format_cents, from_cents, to_cents


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
        for account, credit in self.credits.items():
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

    def balance(self, account):
        """单个账户当前的余额。"""
        return self._balances.get(account, ZERO)

    def balances(self):
        """全部账户余额的副本。"""
        return dict(self._balances)

    def apply_batch(self, batch_id, requests):
        """把一批请求记进账本，返回 BatchResult。"""
        credits = {}
        for request in requests:
            self._post(request, credits)
        balances = {}
        for account, credit in credits.items():
            balance = self._balances.get(account, ZERO) + credit
            self._balances[account] = balance
            balances[account] = balance
        self._requests += len(requests)
        return BatchResult(batch_id, credits, balances)

    def reconcile(self):
        """把请求总额和账户余额合起来对一遍。"""
        total_out = sum(self._balances.values(), ZERO)
        return ReconcileReport(self._requests, self._total_in, total_out)

    def _post(self, request, credits):
        weights = request.weights
        if not weights:
            raise ValueError("请求里没有账户")
        total_cents = to_cents(request.total)
        self._total_in += from_cents(total_cents)
        if total_cents == 0:
            return
        allocation = allocate(from_cents(total_cents), list(weights.values()))
        for account, share in zip(weights, allocation.shares):
            # 入账前把份额折到分，别把更细的尾巴带进余额
            credits[account] = credits.get(account, ZERO) + from_cents(to_cents(share))
        residual = allocation.residual
        if residual < 0:
            target = min(weights, key=lambda name: as_weight(weights[name]))
            credits[target] = credits.get(target, ZERO) + residual
