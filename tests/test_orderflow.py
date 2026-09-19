"""orderflow 行为清单——重构期间一个字都不改，必须原样全绿。"""

import unittest

from orderflow import InvalidTransitionError, Order

EVENTS = ["pay", "ship", "deliver", "cancel", "refund", "close"]

# 每个状态下事件是否合法（全部组合，无例外）
CAN = {
    "created": {"pay": True, "ship": False, "deliver": False, "cancel": True, "refund": False, "close": False},
    "paid": {"pay": False, "ship": True, "deliver": False, "cancel": True, "refund": True, "close": False},
    "shipped": {"pay": False, "ship": False, "deliver": True, "cancel": False, "refund": False, "close": False},
    "delivered": {"pay": False, "ship": False, "deliver": False, "cancel": False, "refund": False, "close": True},
    "cancelled": {"pay": False, "ship": False, "deliver": False, "cancel": False, "refund": False, "close": True},
    "refunded": {"pay": False, "ship": False, "deliver": False, "cancel": False, "refund": False, "close": True},
    "closed": {e: False for e in EVENTS},
}

ALLOWED = {
    "created": ["pay", "cancel"],
    "paid": ["ship", "cancel", "refund"],
    "shipped": ["deliver"],
    "delivered": ["close"],
    "cancelled": ["close"],
    "refunded": ["close"],
    "closed": [],
}


def order_in(state):
    if state == "closed":
        return closed_from("delivered")
    o = Order("T")
    steps = {
        "created": [],
        "paid": [("pay", (100,))],
        "shipped": [("pay", (100,)), ("ship", ("SF",))],
        "delivered": [("pay", (100,)), ("ship", ("SF",)), ("deliver", ("王五",))],
        "cancelled": [("cancel", ())],
        "refunded": [("pay", (100,)), ("refund", ())],
    }
    for name, args in steps[state]:
        getattr(o, name)(*args)
    return o


def closed_from(state):
    o = order_in(state)
    o.close()
    return o


class TestStates(unittest.TestCase):
    def test_initial(self):
        o = Order("SO-1")
        self.assertEqual(o.order_id, "SO-1")
        self.assertEqual(o.state(), "created")
        self.assertFalse(o.is_final())

    def test_state_progression(self):
        o = order_in("paid")
        self.assertEqual(o.state(), "paid")
        self.assertEqual(o.amount, 100)
        o = order_in("shipped")
        self.assertEqual(o.state(), "shipped")
        self.assertEqual(o.carrier, "SF")
        o = order_in("delivered")
        self.assertEqual(o.state(), "delivered")
        self.assertEqual(o.receiver, "王五")

    def test_side_states(self):
        self.assertEqual(order_in("cancelled").state(), "cancelled")
        self.assertEqual(order_in("refunded").state(), "refunded")

    def test_close_from_three_states(self):
        for st in ["delivered", "cancelled", "refunded"]:
            o = closed_from(st)
            self.assertEqual(o.state(), "closed")
            self.assertTrue(o.is_final())

    def test_is_final_only_closed(self):
        for st in ["created", "paid", "shipped", "delivered", "cancelled", "refunded"]:
            self.assertFalse(order_in(st).is_final())


class TestCanMatrix(unittest.TestCase):
    def test_can_matrix(self):
        for st in CAN:
            for e in EVENTS:
                o = order_in(st)
                self.assertEqual(o.can(e), CAN[st][e], "%s/%s" % (st, e))

    def test_can_unknown_event(self):
        with self.assertRaises(ValueError) as cm:
            order_in("created").can("explode")
        self.assertEqual(str(cm.exception), "unknown event: explode")


class TestAllowedEvents(unittest.TestCase):
    def test_allowed_per_state(self):
        for st in ALLOWED:
            o = order_in(st)
            self.assertEqual(o.allowed_events(), ALLOWED[st], st)


class TestTransitions(unittest.TestCase):
    def test_happy_trail(self):
        o = Order("SO-2")
        o.pay(19900)
        o.ship("SF")
        o.deliver("王五")
        o.close()
        self.assertEqual(o.trail(), [
            ("pay", "created", "paid"),
            ("ship", "paid", "shipped"),
            ("deliver", "shipped", "delivered"),
            ("close", "delivered", "closed"),
        ])

    def test_cancel_from_created(self):
        o = order_in("created")
        o.cancel()
        self.assertEqual(o.trail(), [("cancel", "created", "cancelled")])

    def test_cancel_from_paid(self):
        o = order_in("paid")
        o.cancel()
        self.assertEqual(o.trail(), [("pay", "created", "paid"), ("cancel", "paid", "cancelled")])

    def test_refund_then_close(self):
        o = order_in("refunded")
        o.close()
        self.assertEqual(o.trail(), [
            ("pay", "created", "paid"),
            ("refund", "paid", "refunded"),
            ("close", "refunded", "closed"),
        ])

    def test_close_from_cancelled(self):
        o = closed_from("cancelled")
        self.assertEqual(o.trail(), [
            ("cancel", "created", "cancelled"),
            ("close", "cancelled", "closed"),
        ])

    def test_orders_independent(self):
        a = order_in("paid")
        b = order_in("created")
        b.cancel()
        self.assertEqual(a.state(), "paid")
        self.assertEqual(b.state(), "cancelled")


class TestInvalidTransitions(unittest.TestCase):
    def test_pay_invalid_states(self):
        for st, msg in [
            ("paid", "event 'pay' not allowed in state 'paid'"),
            ("shipped", "event 'pay' not allowed in state 'shipped'"),
            ("delivered", "event 'pay' not allowed in state 'delivered'"),
            ("cancelled", "event 'pay' not allowed in state 'cancelled'"),
            ("refunded", "event 'pay' not allowed in state 'refunded'"),
            ("closed", "event 'pay' not allowed in state 'closed'"),
        ]:
            with self.assertRaises(InvalidTransitionError) as cm:
                order_in(st).pay(1)
            self.assertEqual(str(cm.exception), msg, st)

    def test_ship_invalid_states(self):
        for st, msg in [
            ("created", "event 'ship' not allowed in state 'created'"),
            ("shipped", "event 'ship' not allowed in state 'shipped'"),
            ("delivered", "event 'ship' not allowed in state 'delivered'"),
            ("cancelled", "event 'ship' not allowed in state 'cancelled'"),
            ("refunded", "event 'ship' not allowed in state 'refunded'"),
            ("closed", "event 'ship' not allowed in state 'closed'"),
        ]:
            with self.assertRaises(InvalidTransitionError) as cm:
                order_in(st).ship("SF")
            self.assertEqual(str(cm.exception), msg, st)

    def test_deliver_invalid_states(self):
        for st, msg in [
            ("created", "event 'deliver' not allowed in state 'created'"),
            ("paid", "event 'deliver' not allowed in state 'paid'"),
            ("delivered", "event 'deliver' not allowed in state 'delivered'"),
            ("cancelled", "event 'deliver' not allowed in state 'cancelled'"),
            ("refunded", "event 'deliver' not allowed in state 'refunded'"),
            ("closed", "event 'deliver' not allowed in state 'closed'"),
        ]:
            with self.assertRaises(InvalidTransitionError) as cm:
                order_in(st).deliver("王五")
            self.assertEqual(str(cm.exception), msg, st)

    def test_cancel_invalid_states(self):
        for st, msg in [
            ("shipped", "event 'cancel' not allowed in state 'shipped'"),
            ("delivered", "event 'cancel' not allowed in state 'delivered'"),
            ("cancelled", "event 'cancel' not allowed in state 'cancelled'"),
            ("refunded", "event 'cancel' not allowed in state 'refunded'"),
            ("closed", "event 'cancel' not allowed in state 'closed'"),
        ]:
            with self.assertRaises(InvalidTransitionError) as cm:
                order_in(st).cancel()
            self.assertEqual(str(cm.exception), msg, st)

    def test_refund_invalid_states(self):
        for st, msg in [
            ("created", "event 'refund' not allowed in state 'created'"),
            ("shipped", "event 'refund' not allowed in state 'shipped'"),
            ("delivered", "event 'refund' not allowed in state 'delivered'"),
            ("cancelled", "event 'refund' not allowed in state 'cancelled'"),
            ("refunded", "event 'refund' not allowed in state 'refunded'"),
            ("closed", "event 'refund' not allowed in state 'closed'"),
        ]:
            with self.assertRaises(InvalidTransitionError) as cm:
                order_in(st).refund()
            self.assertEqual(str(cm.exception), msg, st)

    def test_close_invalid_states(self):
        for st, msg in [
            ("created", "event 'close' not allowed in state 'created'"),
            ("paid", "event 'close' not allowed in state 'paid'"),
            ("shipped", "event 'close' not allowed in state 'shipped'"),
            ("closed", "event 'close' not allowed in state 'closed'"),
        ]:
            with self.assertRaises(InvalidTransitionError) as cm:
                (closed_from("delivered") if st == "closed" else order_in(st)).close()
            self.assertEqual(str(cm.exception), msg, st)


class TestGuards(unittest.TestCase):
    def test_ship_requires_carrier(self):
        o = order_in("paid")
        for bad in ["", None]:
            with self.assertRaises(InvalidTransitionError) as cm:
                o.ship(bad)
            self.assertEqual(str(cm.exception), "event 'ship' blocked: carrier is required")
        self.assertEqual(o.state(), "paid")
        self.assertEqual(o.trail(), [("pay", "created", "paid")])

    def test_deliver_requires_receiver(self):
        o = order_in("shipped")
        with self.assertRaises(InvalidTransitionError) as cm:
            o.deliver("")
        self.assertEqual(str(cm.exception), "event 'deliver' blocked: receiver is required")
        self.assertEqual(o.state(), "shipped")

    def test_guard_checked_after_state(self):
        with self.assertRaises(InvalidTransitionError) as cm:
            order_in("created").ship("")
        self.assertEqual(str(cm.exception), "event 'ship' not allowed in state 'created'")


class TestPayValidation(unittest.TestCase):
    def test_amount_must_be_positive_int(self):
        for bad in [0, -5, "100", True, 3.5]:
            with self.assertRaises(ValueError) as cm:
                order_in("created").pay(bad)
            self.assertEqual(str(cm.exception), "pay amount must be a positive integer", repr(bad))

    def test_amount_checked_after_state(self):
        with self.assertRaises(InvalidTransitionError):
            order_in("paid").pay(-5)

    def test_failed_pay_leaves_state(self):
        o = order_in("created")
        with self.assertRaises(ValueError):
            o.pay(0)
        self.assertEqual(o.state(), "created")
        self.assertEqual(o.trail(), [])


class TestErrorType(unittest.TestCase):
    def test_error_hierarchy(self):
        self.assertTrue(issubclass(InvalidTransitionError, Exception))


if __name__ == "__main__":
    unittest.main()
