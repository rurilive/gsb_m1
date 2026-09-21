"""Outbox 现有行为的锁定测试。"""

import unittest

from outboxd.outbox import MemoryStore, Outbox


class RecordingSender:
    """记录投递内容的假 sender，可按 seq 指定失败。"""

    def __init__(self, fail_on=()):
        self.sent = []
        self._fail_on = set(fail_on)

    def send(self, row):
        if row["seq"] in self._fail_on:
            raise RuntimeError("boom %s" % row["seq"])
        self.sent.append(row)


class TestRecord(unittest.TestCase):
    def test_record_returns_monotonic_seq(self):
        box = Outbox(MemoryStore(), RecordingSender())
        first = box.record("order-1", "created", {"n": 1})
        second = box.record("order-1", "paid", {"n": 2})
        self.assertEqual((first, second), (1, 2))

    def test_pending_lists_rows_in_seq_order(self):
        store = MemoryStore()
        box = Outbox(store, RecordingSender())
        box.record("a", "x", {})
        box.record("b", "y", {})
        pending = store.pending()
        self.assertEqual([r["seq"] for r in pending], [1, 2])
        self.assertEqual(pending[0]["aggregate"], "a")

    def test_get_missing_returns_none(self):
        self.assertIsNone(MemoryStore().get(99))


class TestRelay(unittest.TestCase):
    def test_delivers_every_pending_row(self):
        store = MemoryStore()
        sender = RecordingSender()
        box = Outbox(store, sender)
        box.record("a", "x", {"n": 1})
        box.record("b", "y", {"n": 2})
        self.assertEqual(box.relay(), 2)
        self.assertEqual([r["seq"] for r in sender.sent], [1, 2])

    def test_success_marks_row_sent(self):
        store = MemoryStore()
        box = Outbox(store, RecordingSender())
        seq = box.record("a", "x", {})
        box.relay()
        self.assertEqual(store.get(seq)["status"], "sent")
        self.assertEqual(store.pending(), [])

    def test_sender_receives_full_row(self):
        store = MemoryStore()
        sender = RecordingSender()
        box = Outbox(store, sender)
        box.record("order-9", "shipped", {"id": 7})
        box.relay()
        row = sender.sent[0]
        self.assertEqual(row["aggregate"], "order-9")
        self.assertEqual(row["kind"], "shipped")
        self.assertEqual(row["payload"], {"id": 7})

    def test_failed_row_stays_pending(self):
        store = MemoryStore()
        box = Outbox(store, RecordingSender(fail_on=[1]))
        box.record("a", "x", {})
        self.assertEqual(box.relay(), 0)
        self.assertEqual(store.get(1)["status"], "pending")

    def test_relay_empty_returns_zero(self):
        box = Outbox(MemoryStore(), RecordingSender())
        self.assertEqual(box.relay(), 0)

    def test_relay_twice_does_not_resend(self):
        store = MemoryStore()
        sender = RecordingSender()
        box = Outbox(store, sender)
        box.record("a", "x", {})
        box.relay()
        self.assertEqual(box.relay(), 0)
        self.assertEqual(len(sender.sent), 1)

    def test_clock_is_injectable(self):
        box = Outbox(MemoryStore(), RecordingSender(), clock=lambda: 123.0)
        box.record("a", "x", {})
        self.assertEqual(box.relay(), 1)

    def test_rows_exposes_status(self):
        store = MemoryStore()
        box = Outbox(store, RecordingSender())
        box.record("a", "x", {})
        box.relay()
        self.assertEqual(store.rows()[0]["status"], "sent")


if __name__ == "__main__":
    unittest.main()
