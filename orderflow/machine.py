"""orderflow: 订单状态机。2019 年跟着第一个下单接口写的，结算/履约/售后三条线共用。

表驱动结构：_TRANSITIONS 是 状态×事件 转移表，守卫与副作用各挂一个函数，
所有事件统一走 Order._fire() 查表入口。加新事件 = 加一行表项（必要时加一个守卫函数）。

行为口径（历史形成的，全部要保住，tests/test_orderflow.py 是清单）：
- 非法转移抛 InvalidTransitionError，文案 "event '<evt>' not allowed in state '<st>'"
- 守卫不过的文案 "event '<evt>' blocked: <原因>"
- can() 对不认识的事件名抛 ValueError
- 事件失败时订单状态与轨迹必须原样不动
"""

from collections import namedtuple


class InvalidTransitionError(Exception):
    """非法转移或守卫不过。文案格式下游在用正则匹配，别动。"""


_Transition = namedtuple("_Transition", ["to", "guard", "action"])

EVENTS = ("pay", "ship", "deliver", "cancel", "refund", "close")

FINAL_STATES = frozenset(["closed"])


def _require_positive_int_amount(order, amount):
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("pay amount must be a positive integer")


def _require_carrier(order, carrier):
    if not isinstance(carrier, str) or carrier == "":
        raise InvalidTransitionError("event 'ship' blocked: carrier is required")


def _require_receiver(order, receiver):
    if not isinstance(receiver, str) or receiver == "":
        raise InvalidTransitionError("event 'deliver' blocked: receiver is required")


def _set_amount(order, amount):
    order.amount = amount


def _set_carrier(order, carrier):
    order.carrier = carrier


def _set_receiver(order, receiver):
    order.receiver = receiver


_TRANSITIONS = {
    "created": {
        "pay": _Transition("paid", _require_positive_int_amount, _set_amount),
        "cancel": _Transition("cancelled", None, None),
    },
    "paid": {
        "ship": _Transition("shipped", _require_carrier, _set_carrier),
        "cancel": _Transition("cancelled", None, None),
        "refund": _Transition("refunded", None, None),
    },
    "shipped": {
        "deliver": _Transition("delivered", _require_receiver, _set_receiver),
    },
    "delivered": {
        "close": _Transition("closed", None, None),
    },
    "cancelled": {
        "close": _Transition("closed", None, None),
    },
    "refunded": {
        "close": _Transition("closed", None, None),
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

    def state(self):
        return self._state

    def is_final(self):
        return self._state in FINAL_STATES

    def allowed_events(self):
        return [event for event in EVENTS if self.can(event)]

    def can(self, event):
        if event not in EVENTS:
            raise ValueError("unknown event: %s" % event)
        return event in _TRANSITIONS[self._state]

    def _fire(self, event, *args):
        transition = _TRANSITIONS[self._state].get(event)
        if transition is None:
            raise InvalidTransitionError(
                "event '%s' not allowed in state '%s'" % (event, self._state)
            )
        if transition.guard is not None:
            transition.guard(self, *args)
        if transition.action is not None:
            transition.action(self, *args)
        frm = self._state
        self._state = transition.to
        self._trail.append((event, frm, transition.to))

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
