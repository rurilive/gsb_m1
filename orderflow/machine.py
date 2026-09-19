"""orderflow: 订单状态机。2019 年跟着第一个下单接口写的，结算/履约/售后三条线共用。

结构：表驱动。_TRANSITIONS 是 状态×事件 的转移表，每条转移带目标状态、
守卫（guard，可选）与副作用（effect，可选）；所有事件统一走 Order._fire 查表。

行为口径（历史形成的，全部要保住，tests/test_orderflow.py 是清单）：
- 非法转移抛 InvalidTransitionError，文案 "event '<evt>' not allowed in state '<st>'"
- 守卫不过的文案 "event '<evt>' blocked: <原因>"
- can() 对不认识的事件名抛 ValueError
- 事件失败时订单状态与轨迹必须原样不动
"""


class InvalidTransitionError(Exception):
    """非法转移或守卫不过。文案格式下游在用正则匹配，别动。"""


_EVENT_NAMES = ["pay", "ship", "deliver", "cancel", "refund", "close"]


def _validate_amount(order, amount):
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("pay amount must be a positive integer")


def _require_carrier(order, carrier):
    if not isinstance(carrier, str) or carrier == "":
        raise InvalidTransitionError("event 'ship' blocked: carrier is required")


def _require_receiver(order, receiver):
    if not isinstance(receiver, str) or receiver == "":
        raise InvalidTransitionError("event 'deliver' blocked: receiver is required")


def _store_amount(order, amount):
    order.amount = amount


def _store_carrier(order, carrier):
    order.carrier = carrier


def _store_receiver(order, receiver):
    order.receiver = receiver


class _Transition(object):
    """一条转移：目标状态 + 守卫（先查，可选）+ 副作用（后执行，可选）。"""

    def __init__(self, target, guard=None, effect=None):
        self.target = target
        self.guard = guard
        self.effect = effect


# 转移表：当前状态 -> 事件 -> _Transition。查不到就是非法转移。
_TRANSITIONS = {
    "created": {
        "pay": _Transition("paid", guard=_validate_amount, effect=_store_amount),
        "cancel": _Transition("cancelled"),
    },
    "paid": {
        "ship": _Transition("shipped", guard=_require_carrier, effect=_store_carrier),
        "cancel": _Transition("cancelled"),
        "refund": _Transition("refunded"),
    },
    "shipped": {
        "deliver": _Transition("delivered", guard=_require_receiver, effect=_store_receiver),
    },
    "delivered": {
        "close": _Transition("closed"),
    },
    "cancelled": {
        "close": _Transition("closed"),
    },
    "refunded": {
        "close": _Transition("closed"),
    },
    "closed": {},
}


class Order(object):
    def __init__(self, order_id):
        self.order_id = order_id
        self._state = "created"
        self.amount = None
        self.carrier = None
        self.receiver = None
        self._trail = []

    # 六个历史旗标保留为只读属性：对应事件成功过即为真，与旧实现语义一致。
    @property
    def _paid(self):
        return self._fired("pay")

    @property
    def _shipped(self):
        return self._fired("ship")

    @property
    def _delivered(self):
        return self._fired("deliver")

    @property
    def _cancelled(self):
        return self._fired("cancel")

    @property
    def _refunded(self):
        return self._fired("refund")

    @property
    def _closed(self):
        return self._fired("close")

    def _fired(self, event):
        return any(step[0] == event for step in self._trail)

    def state(self):
        return self._state

    def is_final(self):
        return self._state == "closed"

    def allowed_events(self):
        return [name for name in _EVENT_NAMES if self.can(name)]

    def can(self, event):
        if event not in _EVENT_NAMES:
            raise ValueError("unknown event: %s" % event)
        return event in _TRANSITIONS[self._state]

    def _forbid(self, event):
        raise InvalidTransitionError(
            "event '%s' not allowed in state '%s'" % (event, self._state)
        )

    def _fire(self, event, *args):
        transition = _TRANSITIONS[self._state].get(event)
        if transition is None:
            self._forbid(event)
        if transition.guard is not None:
            transition.guard(self, *args)
        if transition.effect is not None:
            transition.effect(self, *args)
        frm = self._state
        self._state = transition.target
        self._trail.append((event, frm, transition.target))

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
