"""orderflow: 订单状态机。2019 年跟着第一个下单接口写的，结算/履约/售后三条线共用。

行为口径（历史形成的，全部要保住，tests/test_orderflow.py 是清单）：
- 状态由 _paid/_shipped/_delivered/_cancelled/_refunded/_closed 六个旗标组合表达，没有单独的状态字段
- 非法转移抛 InvalidTransitionError，文案 "event '<evt>' not allowed in state '<st>'"
- 守卫不过的文案 "event '<evt>' blocked: <原因>"
- can() 对不认识的事件名抛 ValueError
- 事件失败时订单状态与轨迹必须原样不动
"""


class InvalidTransitionError(Exception):
    """非法转移或守卫不过。文案格式下游在用正则匹配，别动。"""


class Order(object):
    def __init__(self, order_id):
        self.order_id = order_id
        self._paid = False
        self._shipped = False
        self._delivered = False
        self._cancelled = False
        self._refunded = False
        self._closed = False
        self.amount = None
        self.carrier = None
        self.receiver = None
        self._trail = []

    def state(self):
        if self._closed:
            return "closed"
        if self._refunded:
            return "refunded"
        if self._cancelled:
            return "cancelled"
        if self._delivered:
            return "delivered"
        if self._shipped:
            return "shipped"
        if self._paid:
            return "paid"
        return "created"

    def is_final(self):
        return self._closed

    def allowed_events(self):
        names = ["pay", "ship", "deliver", "cancel", "refund", "close"]
        out = []
        for n in names:
            if self.can(n):
                out.append(n)
        return out

    def can(self, event):
        if event == "pay":
            if self._paid or self._shipped or self._delivered:
                return False
            if self._cancelled or self._refunded or self._closed:
                return False
            return True
        if event == "ship":
            if not self._paid:
                return False
            if self._shipped or self._delivered:
                return False
            if self._cancelled or self._refunded or self._closed:
                return False
            return True
        if event == "deliver":
            if not self._shipped:
                return False
            if self._delivered or self._cancelled or self._refunded or self._closed:
                return False
            return True
        if event == "cancel":
            if self._shipped or self._delivered:
                return False
            if self._cancelled or self._refunded or self._closed:
                return False
            return True
        if event == "refund":
            if not self._paid:
                return False
            if self._shipped or self._delivered or self._refunded or self._cancelled or self._closed:
                return False
            return True
        if event == "close":
            if self._delivered or self._cancelled or self._refunded:
                if self._closed:
                    return False
                return True
            return False
        raise ValueError("unknown event: %s" % event)

    def _forbid(self, event):
        raise InvalidTransitionError(
            "event '%s' not allowed in state '%s'" % (event, self.state())
        )

    def pay(self, amount):
        if self._paid:
            if self._shipped:
                self._forbid("pay")
            if self._delivered:
                self._forbid("pay")
            if self._refunded:
                self._forbid("pay")
            self._forbid("pay")
        if self._cancelled or self._closed:
            self._forbid("pay")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("pay amount must be a positive integer")
        self.amount = amount
        self._paid = True
        self._trail.append(("pay", "created", "paid"))

    def ship(self, carrier):
        if not self.can("ship"):
            self._forbid("ship")
        if not isinstance(carrier, str) or carrier == "":
            raise InvalidTransitionError("event 'ship' blocked: carrier is required")
        self.carrier = carrier
        self._shipped = True
        self._trail.append(("ship", "paid", "shipped"))

    def deliver(self, receiver):
        if not self.can("deliver"):
            self._forbid("deliver")
        if not isinstance(receiver, str) or receiver == "":
            raise InvalidTransitionError("event 'deliver' blocked: receiver is required")
        self.receiver = receiver
        self._delivered = True
        self._trail.append(("deliver", "shipped", "delivered"))

    def cancel(self):
        if not self.can("cancel"):
            self._forbid("cancel")
        frm = "created"
        if self._paid:
            frm = "paid"
        self._cancelled = True
        self._trail.append(("cancel", frm, "cancelled"))

    def refund(self):
        if not self.can("refund"):
            self._forbid("refund")
        self._refunded = True
        self._trail.append(("refund", "paid", "refunded"))

    def close(self):
        if not self.can("close"):
            self._forbid("close")
        frm = "delivered"
        if self._cancelled:
            frm = "cancelled"
        elif self._refunded:
            frm = "refunded"
        self._closed = True
        self._trail.append(("close", frm, "closed"))

    def trail(self):
        return list(self._trail)
