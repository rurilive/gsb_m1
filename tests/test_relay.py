"""可靠投递中继的行为测试：退避、死信、租约与分区顺序。"""

import threading
import unittest

from outboxd.outbox import MemoryStore, Outbox


class FakeClock:
    """可手动推进的假时钟，relay 不真实 sleep。"""

    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class ScriptedSender:
    """按 seq 脚本失败：flaky[seq] 为前几次投递要失败的次数。"""

    def __init__(self, flaky=None):
        self.sent = []
        self._flaky = dict(flaky or {})

    def send(self, row):
        remaining = self._flaky.get(row["seq"], 0)
        if remaining > 0:
            self._flaky[row["seq"]] = remaining - 1
            raise RuntimeError("rejected %s" % row["seq"])
        self.sent.append(row)


def make_box(store, sender, clock, **kwargs):
    options = dict(
        max_attempts=5,
        backoff_base=1.0,
        backoff_cap=100.0,
        lease_seconds=30.0,
    )
    options.update(kwargs)
    return Outbox(store, sender, clock=clock, **options)


class TestBackoff(unittest.TestCase):
    def test_failure_not_retried_until_backoff_moment(self):
        clock = FakeClock(1000.0)
        store = MemoryStore()
        sender = ScriptedSender(flaky={1: 1})
        box = make_box(store, sender, clock)
        box.record("a", "e1", {})
        box.record("a", "e2", {})

        self.assertEqual(box.relay(), 0)
        self.assertEqual(store.get(1)["attempts"], 1)
        self.assertEqual(store.get(1)["not_before"], 1001.0)

        # 退避时刻未到：同分区两条都不动。
        clock.advance(0.9)
        self.assertEqual(box.relay(), 0)
        self.assertEqual([r["seq"] for r in sender.sent], [])

        # 一到退避时刻：旧事件先发，成功后新事件紧跟，顺序仍是 1,2。
        clock.advance(0.1)
        self.assertEqual(box.relay(), 2)
        self.assertEqual([r["seq"] for r in sender.sent], [1, 2])
        self.assertEqual(store.get(1)["status"], "sent")

    def test_backoff_delay_doubles_then_caps(self):
        clock = FakeClock(0.0)
        store = MemoryStore()
        sender = ScriptedSender(flaky={1: 5})
        box = make_box(store, sender, clock,
                       backoff_base=2.0, backoff_cap=10.0, max_attempts=10)
        box.record("a", "x", {})

        box.relay()
        self.assertEqual(store.get(1)["not_before"], 2.0)   # 2 * 2**0
        clock.t = 2.0
        box.relay()
        self.assertEqual(store.get(1)["not_before"], 6.0)   # 2 + 2 * 2**1
        clock.t = 6.0
        box.relay()
        self.assertEqual(store.get(1)["not_before"], 14.0)  # 6 + 2 * 2**2
        clock.t = 14.0
        box.relay()
        self.assertEqual(store.get(1)["not_before"], 24.0)  # 封顶 10


class TestDeadLetter(unittest.TestCase):
    def test_row_dies_at_max_attempts_with_error_recorded(self):
        clock = FakeClock(0.0)
        store = MemoryStore()
        sender = ScriptedSender(flaky={1: 99})
        box = make_box(store, sender, clock,
                       backoff_base=1.0, max_attempts=3)
        box.record("a", "x", {})

        box.relay()                       # 第 1 次失败
        clock.t = 1.0
        box.relay()                       # 第 2 次失败
        clock.t = 3.0
        delivered = box.relay()           # 第 3 次失败 -> 死信

        self.assertEqual(delivered, 0)
        row = store.get(1)
        self.assertEqual(row["status"], "dead")
        self.assertEqual(row["attempts"], 3)
        self.assertIn("rejected 1", row["last_error"])
        self.assertEqual([r["seq"] for r in store.dead()], [1])
        self.assertNotIn(1, [r["seq"] for r in store.pending()])

    def test_dead_row_unblocks_same_aggregate_in_same_run(self):
        clock = FakeClock(0.0)
        store = MemoryStore()
        sender = ScriptedSender(flaky={1: 99})
        box = make_box(store, sender, clock,
                       backoff_base=1.0, max_attempts=1)
        box.record("a", "old", {})
        box.record("a", "new", {})
        box.record("b", "other", {})

        # seq=1 首次即死信，分区解除；本轮 seq=2 立刻发出，
        # seq=3 属于另一分区，本就不受影响。
        self.assertEqual(box.relay(), 2)
        self.assertEqual(store.get(1)["status"], "dead")
        self.assertEqual([r["seq"] for r in sender.sent], [2, 3])
        self.assertEqual(store.pending(), [])


class TestOrdering(unittest.TestCase):
    def test_same_aggregate_waits_for_predecessor(self):
        clock = FakeClock(0.0)
        store = MemoryStore()
        sender = ScriptedSender(flaky={1: 1})
        box = make_box(store, sender, clock)
        box.record("a", "e1", {})
        box.record("a", "e2", {})
        box.record("a", "e3", {})
        box.record("b", "other", {})

        box.relay()
        # seq=1 退避中，同分区的 2、3 一律不许抢先；分区 b 不受牵连。
        self.assertEqual([r["seq"] for r in sender.sent], [4])

        clock.t = 1.0
        self.assertEqual(box.relay(), 3)
        self.assertEqual([r["seq"] for r in sender.sent], [4, 1, 2, 3])
        self.assertEqual(
            [r["status"] for r in store.rows()],
            ["sent", "sent", "sent", "sent"])


class TestLease(unittest.TestCase):
    def test_foreign_valid_lease_blocks_claim(self):
        clock = FakeClock(100.0)
        store = MemoryStore()
        sender = ScriptedSender()
        box = make_box(store, sender, clock, lease_seconds=30.0)
        box.record("a", "locked", {})
        box.record("a", "next", {})

        # 另一个中继持着 seq=1 的有效租约（投递中崩溃/在途）。
        self.assertIsNotNone(
            store.claim(1, "other-relay", 100.0, lease_seconds=30.0))

        self.assertEqual(box.relay(), 0)
        self.assertEqual(sender.sent, [])
        self.assertEqual(store.get(1)["status"], "pending")

    def test_expired_lease_can_be_reclaimed(self):
        clock = FakeClock(100.0)
        store = MemoryStore()
        sender = ScriptedSender()
        box = make_box(store, sender, clock, lease_seconds=30.0)
        box.record("a", "locked", {})
        box.record("a", "next", {})
        store.claim(1, "crashed-relay", 100.0, lease_seconds=30.0)

        clock.t = 129.0
        self.assertEqual(box.relay(), 0)
        clock.t = 130.0
        self.assertEqual(box.relay(), 2)
        self.assertEqual([r["seq"] for r in sender.sent], [1, 2])

    def test_concurrent_relays_deliver_each_row_once(self):
        store = MemoryStore()
        sender = ScriptedSender()
        for agg in ("a", "b"):
            for kind in ("e1", "e2", "e3", "e4"):
                store.append(agg, kind, {})

        winners = []

        def worker():
            box = Outbox(store, sender, clock=lambda: 0.0,
                         lease_seconds=30.0)
            for _ in range(100):
                box.relay()
                if not store.pending():
                    winners.append(threading.get_ident())
                    return

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5.0)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(sender.sent), 8)
        self.assertEqual(sorted(r["seq"] for r in sender.sent),
                         list(range(1, 9)))
        self.assertTrue(winners)


if __name__ == "__main__":
    unittest.main()
