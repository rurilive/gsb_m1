"""SyncBus 订阅与分发口径的锁定测试。"""

import unittest

from eventwire.bus import SyncBus


def recorder(log, name):
    def handler(topic, payload):
        log.append((name, topic, payload))
    return handler


class TestSubscribe(unittest.TestCase):
    def test_new_name_flag(self):
        bus = SyncBus()
        self.assertTrue(bus.subscribe("audit", recorder([], "audit")))
        self.assertFalse(bus.subscribe("audit", recorder([], "audit")))

    def test_resubscribe_replaces_handler_and_keeps_position(self):
        bus = SyncBus()
        log = []
        bus.subscribe("first", recorder(log, "old"))
        bus.subscribe("second", recorder(log, "second"))
        bus.subscribe("first", recorder(log, "new"))
        self.assertEqual(bus.subscriber_names(), ("first", "second"))
        bus.publish("tick", 1)
        self.assertEqual(log, [("new", "tick", 1), ("second", "tick", 1)])

    def test_default_pattern_covers_everything(self):
        bus = SyncBus()
        log = []
        bus.subscribe("all", recorder(log, "all"))
        bus.publish("a.b.c", 1)
        self.assertEqual(len(log), 1)

    def test_invalid_arguments(self):
        bus = SyncBus()
        with self.assertRaises(ValueError):
            bus.subscribe("", recorder([], "x"))
        with self.assertRaises(TypeError):
            bus.subscribe("a", "not-callable")
        with self.assertRaises(TypeError):
            bus.subscribe("a", recorder([], "x"), pattern=3)
        with self.assertRaises(ValueError):
            bus.subscribe("a", recorder([], "x"), pattern="a..b")
        with self.assertRaises(ValueError):
            bus.subscribe("a", recorder([], "x"), pattern="a.**.b")


class TestPublish(unittest.TestCase):
    def test_dispatch_follows_subscribe_order(self):
        bus = SyncBus()
        log = []
        for name in ["one", "two", "three"]:
            bus.subscribe(name, recorder(log, name))
        bus.publish("tick", {"n": 1})
        self.assertEqual([entry[0] for entry in log], ["one", "two", "three"])

    def test_pattern_filters_dispatch(self):
        bus = SyncBus()
        log = []
        bus.subscribe("orders", recorder(log, "orders"), "order.**")
        bus.subscribe("paid", recorder(log, "paid"), "order.paid")
        delivered = bus.publish("order.paid", 7)
        self.assertEqual(delivered, 2)
        delivered = bus.publish("user.created", 7)
        self.assertEqual(delivered, 0)
        self.assertEqual([entry[0] for entry in log], ["orders", "paid"])

    def test_payload_passed_through_untouched(self):
        bus = SyncBus()
        log = []
        bus.subscribe("keeper", recorder(log, "keeper"))
        payload = {"id": 9, "tags": ["a"]}
        bus.publish("tick", payload)
        self.assertIs(log[0][2], payload)

    def test_invalid_topic_rejected(self):
        bus = SyncBus()
        with self.assertRaises(ValueError):
            bus.publish("a..b", 1)
        with self.assertRaises(ValueError):
            bus.publish("a.*", 1)

    def test_unsubscribe(self):
        bus = SyncBus()
        log = []
        bus.subscribe("keeper", recorder(log, "keeper"))
        bus.subscribe("gone", recorder(log, "gone"))
        self.assertTrue(bus.unsubscribe("gone"))
        self.assertFalse(bus.unsubscribe("gone"))
        bus.publish("tick", 1)
        self.assertEqual([entry[0] for entry in log], ["keeper"])


class TestFailures(unittest.TestCase):
    def test_failing_handler_does_not_stop_others(self):
        bus = SyncBus()
        log = []

        def broken(topic, payload):
            log.append(("broken", topic, payload))
            raise RuntimeError("下游炸了")

        bus.subscribe("broken", broken)
        bus.subscribe("keeper", recorder(log, "keeper"))
        with self.assertRaises(RuntimeError):
            bus.publish("tick", 1)
        self.assertEqual([entry[0] for entry in log], ["broken", "keeper"])

    def test_first_failure_is_reraised(self):
        bus = SyncBus()

        def first(topic, payload):
            raise KeyError("第一个")

        def second(topic, payload):
            raise IndexError("第二个")

        bus.subscribe("first", first)
        bus.subscribe("second", second)
        with self.assertRaises(KeyError):
            bus.publish("tick", 1)

    def test_subscription_changes_during_dispatch_do_not_apply(self):
        bus = SyncBus()
        log = []

        def leaving(topic, payload):
            log.append("leaving")
            bus.unsubscribe("later")

        bus.subscribe("leaving", leaving)
        bus.subscribe("later", recorder(log, "later"))
        bus.publish("tick", 1)
        self.assertEqual(log, ["leaving", ("later", "tick", 1)])
        self.assertEqual(bus.subscriber_names(), ("leaving",))


if __name__ == "__main__":
    unittest.main()
