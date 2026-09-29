"""topichub 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from topichub.hub import TopicHub


def collect():
    """造一个把收到的 Message 收进列表的回调，连列表一起返回。"""
    seen = []

    def handler(message):
        seen.append(message)

    return seen, handler


class TestTopicHub(unittest.TestCase):
    def test_subscribe_returns_handle(self):
        hub = TopicHub()
        _, handler = collect()
        sub = hub.subscribe("orders", handler)
        self.assertEqual(sub.topic, "orders")
        self.assertTrue(sub.active)
        self.assertIs(sub.handler, handler)

    def test_subscribe_rejects_non_callable(self):
        hub = TopicHub()
        with self.assertRaises(TypeError):
            hub.subscribe("orders", 7)

    def test_publish_returns_increasing_seq(self):
        hub = TopicHub()
        self.assertEqual(hub.publish("orders", {"id": 1}), 1)
        self.assertEqual(hub.publish("orders", {"id": 2}), 2)

    def test_handler_receives_message_fields(self):
        hub = TopicHub()
        seen, handler = collect()
        hub.subscribe("orders", handler)
        hub.publish("orders", {"id": 9})
        self.assertEqual(len(seen), 1)
        msg = seen[0]
        self.assertEqual(msg.topic, "orders")
        self.assertEqual(msg.payload, {"id": 9})
        self.assertEqual(msg.seq, 1)

    def test_publish_without_subscribers_ok(self):
        hub = TopicHub()
        self.assertEqual(hub.publish("nobody", "x"), 1)

    def test_payload_default_none(self):
        hub = TopicHub()
        seen, handler = collect()
        hub.subscribe("orders", handler)
        hub.publish("orders")
        self.assertIsNone(seen[0].payload)

    def test_seq_shared_across_topics(self):
        hub = TopicHub()
        self.assertEqual(hub.publish("a"), 1)
        self.assertEqual(hub.publish("b"), 2)
        self.assertEqual(hub.publish("a"), 3)

    def test_unsubscribe_returns_true_then_false(self):
        hub = TopicHub()
        _, handler = collect()
        sub = hub.subscribe("orders", handler)
        self.assertTrue(sub.unsubscribe())
        self.assertFalse(sub.unsubscribe())
        self.assertFalse(sub.active)

    def test_unsubscribed_handler_not_called(self):
        hub = TopicHub()
        seen, handler = collect()
        sub = hub.subscribe("orders", handler)
        hub.publish("orders", 1)
        sub.unsubscribe()
        hub.publish("orders", 2)
        self.assertEqual(len(seen), 1)

    def test_unsubscribe_foreign_handle_false(self):
        hub = TopicHub()
        other = TopicHub()
        _, handler = collect()
        sub = other.subscribe("orders", handler)
        self.assertFalse(hub.unsubscribe(sub))

    def test_handler_exception_recorded(self):
        hub = TopicHub()

        def boom(message):
            raise RuntimeError("boom")

        hub.subscribe("orders", boom)
        hub.publish("orders", 1)
        self.assertTrue(any(isinstance(e, RuntimeError) for e in hub.errors))

    def test_handler_exception_does_not_block_others(self):
        hub = TopicHub()

        def boom(message):
            raise RuntimeError("boom")

        seen, handler = collect()
        hub.subscribe("orders", boom)
        hub.subscribe("orders", handler)
        hub.publish("orders", 1)
        self.assertEqual(len(seen), 1)

    def test_subscriber_count_tracks_active(self):
        hub = TopicHub()
        _, h1 = collect()
        _, h2 = collect()
        s1 = hub.subscribe("orders", h1)
        hub.subscribe("orders", h2)
        self.assertEqual(hub.subscriber_count("orders"), 2)
        s1.unsubscribe()
        self.assertEqual(hub.subscriber_count("orders"), 1)

    def test_pending_zero_on_fresh_hub(self):
        hub = TopicHub()
        self.assertEqual(hub.pending(), 0)


if __name__ == "__main__":
    unittest.main()
