"""多账户账本：按批接收分摊请求，维护余额并提供对账。

账本内部一律用整数分记账，Decimal 金额只在进出账本的边界上换算。
"""

from .allocate import allocate_cents, as_amount, as_weight
from .money import format_cents, from_cents, to_cents


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
            lines.append("%s credit=%s balance=%s" % (
                account,
                format_cents(to_cents(self.credits[account])),
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
    """按批记账的账户集合。

    内部余额、入账总额都是整数分；批次号幂等，同一个 batch_id
    重放时直接返回首次的结果，不重复记账。
    """

    def __init__(self):
        self._balances = {}
        self._total_in_cents = 0
        self._requests = 0
        self._batches = {}

    def balance(self, account):
        """单个账户当前的余额。"""
        return from_cents(self._balances.get(account, 0))

    def balances(self):
        """全部账户余额的副本。"""
        return {
            account: from_cents(cents)
            for account, cents in self._balances.items()
        }

    def apply_batch(self, batch_id, requests):
        """把一批请求记进账本，返回 BatchResult。

        同一个 batch_id 重放时返回首次的结果，余额、请求数、入账
        总额都不重复累计，输出文本逐字节相同。整批先校验再记账，
        校验不过整批不落账。
        """
        if batch_id in self._batches:
            return self._batches[batch_id]
        prepared = []
        for request in requests:
            weights = request.weights
            if not weights:
                raise ValueError("请求里没有账户")
            accounts = sorted(weights)
            prepared.append((
                request,
                accounts,
                [as_weight(weights[account]) for account in accounts],
            ))
        credits = {}
        for request, accounts, parsed_weights in prepared:
            self._post(request, accounts, parsed_weights, credits)
        balances = {}
        for account, credit in credits.items():
            balance = self._balances.get(account, 0) + credit
            self._balances[account] = balance
            balances[account] = balance
        self._requests += len(requests)
        result = BatchResult(
            batch_id,
            {account: from_cents(credit)
             for account, credit in credits.items()},
            {account: from_cents(balance)
             for account, balance in balances.items()},
        )
        self._batches[batch_id] = result
        return result

    def reconcile(self):
        """把请求总额和账户余额合起来对一遍。"""
        total_out = sum(self._balances.values(), 0)
        return ReconcileReport(
            self._requests,
            from_cents(self._total_in_cents),
            from_cents(total_out),
        )

    def _post(self, request, accounts, parsed_weights, credits):
        total_cents = to_cents(request.total)
        self._total_in_cents += total_cents
        if total_cents == 0:
            # 总额折到分之后是零（含不足一分的请求）：各户记一笔
            # 零，账面留个痕迹，请求照常计数
            for account in accounts:
                credits.setdefault(account, 0)
            return
        shares, residual, weight_ints = allocate_cents(
            total_cents, parsed_weights)
        if residual and max(weight_ints) > 0:
            # 尾差归权重最大的账户；accounts 已按账户名排序，并列时
            # 取下标最小的，即账户名排序靠前的。权重全为零时整笔
            # 挂账，尾差不落给任何账户。
            target = max(
                range(len(accounts)),
                key=lambda index: (weight_ints[index], -index),
            )
            shares[target] += residual
        for account, share in zip(accounts, shares):
            credits[account] = credits.get(account, 0) + share
