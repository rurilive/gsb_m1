"""orderflow: 订单状态机。2019 年跟着第一个下单接口写的，结算/履约/售后三条线共用。

表驱动结构：唯一状态字段 _state，所有事件统一走 _fire() 查 _TRANSITIONS。

行为口径（历史形成的，全部要保住，tests/test_orderflow.py 是清单）：
- 非法转移抛 InvalidTransitionError，文案 "event '<evt>' not allowed in state '<st>'"
- 守卫不过的文案 "event '<evt>' blocked: <原因>"，守卫在状态检查之后执行
- can() 对不认识的事件名抛 ValueError
- 事件失败时订单状态与轨迹必须原样不动
- _paid/_shipped/_delivered/_cancelled/_refunded/_closed 六个旗标属性保留，
  随转移同步置位（外部有代码在读，不作为判断依据）
"""


class InvalidTransitionError(Exception):
    """非法转移或守卫不过。文案格式下游在用正则匹配，别动。"""


# 事件顺序即 allowed_events() 的输出顺序，新增事件追加在末尾。
_EVENTS = ("pay", "ship", "deliver", "cancel", "refund", "close")

# 转移表：事件 -> {源状态: 目标状态}。查不到 (事件, 当前状态) 即非法转移。
_TRANSITIONS = {
    "pay": {"created": "paid"},
    "ship": {"paid": "shipped"},
    "deliver": {"shipped": "delivered"},
    "cancel": {"created": "cancelled", "paid": "cancelled"},
    "refund": {"paid": "refunded"},
    "close": {"delivered": "closed", "cancelled": "closed", "refunded": "closed"},
}

# 每个事件置位的历史旗标（仅为兼容保留，逻辑不读它们）。
_FLAG_BY_EVENT = {
    "pay": "_paid",
    "ship": "_shipped",
    "deliver": "_delivered",
    "cancel": "_cancelled",
    "refund": "_refunded",
    "close": "_closed",
}


def _guard_pay(order, amount):
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("pay amount must be a positive integer")


def _guard_ship(order, carrier):
    if not isinstance(carrier, str) or carrier == "":
        raise InvalidTransitionError("event 'ship' blocked: carrier is required")


def _guard_deliver(order, receiver):
    if not isinstance(receiver, str) or receiver == "":
        raise InvalidTransitionError("event 'deliver' blocked: receiver is required")


# 守卫：事件 -> 函数(order, *args)，状态检查通过后、转移执行前调用。
_GUARDS = {
    "pay": _guard_pay,
    "ship": _guard_ship,
    "deliver": _guard_deliver,
}


def _apply_pay(order, amount):
    order.amount = amount


def _apply_ship(order, carrier):
    order.carrier = carrier


def _apply_deliver(order, receiver):
    order.receiver = receiver


# 副作用：事件 -> 函数(order, *args)，守卫通过后、状态落位前调用。
_ACTIONS = {
    "pay": _apply_pay,
    "ship": _apply_ship,
    "deliver": _apply_deliver,
}


class Order(object):
    def __init__(self, order_id):
        self.order_id = order_id
        self._state = "created"
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
        return self._state

    def is_final(self):
        return self._state == "closed"

    def allowed_events(self):
        return [event for event in _EVENTS if self.can(event)]

    def can(self, event):
        if event not in _TRANSITIONS:
            raise ValueError("unknown event: %s" % event)
        return self._state in _TRANSITIONS[event]

    def _forbid(self, event):
        raise InvalidTransitionError(
            "event '%s' not allowed in state '%s'" % (event, self._state)
        )

    def _fire(self, event, *args):
        targets = _TRANSITIONS[event]
        frm = self._state
        if frm not in targets:
            self._forbid(event)
        guard = _GUARDS.get(event)
        if guard is not None:
            guard(self, *args)
        action = _ACTIONS.get(event)
        if action is not None:
            action(self, *args)
        to = targets[frm]
        self._state = to
        setattr(self, _FLAG_BY_EVENT[event], True)
        self._trail.append((event, frm, to))

    def pay(self, amount):
        self._fire("pay", amount)

    def ship(self, carrier):
        self._fire("ship", carrier)

    def deliver(self, receiver):
        self._fire("deliver", receiver)

    def cancel(self):
        self._fire("cancel")

    def refund(self):
        self._fire("refund")

    def close(self):
        self._fire("close")

    def trail(self):
        return list(self._trail)
