"""MessageBus 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from buskit.broker import MessageBus, Message


class Recorder:
    """把收到的消息按顺序记下来。"""

    def __init__(self):
        self.received = []

    def __call__(self, msg):
        self.received.append(msg)


class TestSubscribe(unittest.TestCase):
    def test_publish_reaches_subscriber(self):
        bus = MessageBus()
        rec = Recorder()
        bus.subscribe("orders", rec)
        bus.publish("orders", {"id": 1})
        self.assertEqual(len(rec.received), 1)
        self.assertEqual(rec.received[0].payload, {"id": 1})

    def test_publish_returns_increasing_seq(self):
        bus = MessageBus()
        bus.subscribe("orders", Recorder())
        self.assertEqual(bus.publish("orders", "a"), 1)
        self.assertEqual(bus.publish("orders", "b"), 2)

    def test_seq_is_per_topic(self):
        bus = MessageBus()
        bus.subscribe("orders", Recorder())
        bus.subscribe("events", Recorder())
        self.assertEqual(bus.publish("orders", "a"), 1)
        self.assertEqual(bus.publish("events", "x"), 1)

    def test_publish_without_subscriber_is_allowed(self):
        bus = MessageBus()
        self.assertEqual(bus.publish("nobody", "x"), 1)


class TestMultipleSubscribers(unittest.TestCase):
    def test_all_subscribers_get_message(self):
        bus = MessageBus()
        a = Recorder()
        b = Recorder()
        bus.subscribe("orders", a)
        bus.subscribe("orders", b)
        bus.publish("orders", "x")
        self.assertEqual(len(a.received), 1)
        self.assertEqual(len(b.received), 1)

    def test_subscriber_error_does_not_stop_others(self):
        bus = MessageBus()

        def boom(msg):
            raise RuntimeError("boom")

        rec = Recorder()
        bus.subscribe("orders", boom)
        bus.subscribe("orders", rec)
        bus.publish("orders", "x")
        self.assertEqual(len(rec.received), 1)
        self.assertEqual(len(bus.errors), 1)

    def test_subscriber_count(self):
        bus = MessageBus()
        bus.subscribe("orders", Recorder())
        bus.subscribe("orders", Recorder())
        self.assertEqual(bus.subscriber_count("orders"), 2)


class TestUnsubscribe(unittest.TestCase):
    def test_unsubscribe_stops_delivery(self):
        bus = MessageBus()
        rec = Recorder()
        sub = bus.subscribe("orders", rec)
        bus.publish("orders", "x")
        self.assertTrue(sub.unsubscribe())
        bus.publish("orders", "y")
        self.assertEqual(len(rec.received), 1)

    def test_double_unsubscribe_returns_false(self):
        bus = MessageBus()
        sub = bus.subscribe("orders", Recorder())
        self.assertTrue(sub.unsubscribe())
        self.assertFalse(sub.unsubscribe())

    def test_unsubscribe_count_drops(self):
        bus = MessageBus()
        sub = bus.subscribe("orders", Recorder())
        sub.unsubscribe()
        self.assertEqual(bus.subscriber_count("orders"), 0)


class TestMessage(unittest.TestCase):
    def test_message_carries_topic_and_seq(self):
        bus = MessageBus()
        rec = Recorder()
        bus.subscribe("orders", rec)
        bus.publish("orders", "p")
        msg = rec.received[0]
        self.assertIsInstance(msg, Message)
        self.assertEqual(msg.topic, "orders")
        self.assertEqual(msg.seq, 1)
        self.assertEqual(msg.payload, "p")


if __name__ == "__main__":
    unittest.main()