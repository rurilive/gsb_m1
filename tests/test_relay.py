"""可靠中继行为测试：退避、死信、租约互斥、聚合键内顺序。

时刻一律用注入的假时钟推进，中继不睡眠。
"""

import threading
import unittest

from outboxd.outbox import MemoryStore, Outbox, STATUS_DEAD


class FakeClock:
    """可手动推进的假时钟，初值 0。"""

    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class ScriptedSender:
    """按脚本失败的假 sender。

    fail_seq 始终失败；flaky_seq 先失败指定次数后恢复成功。
    同时记录每次投递的（时刻, seq），便于断言退避时刻。
    """

    def __init__(self, fail_seq=(), flaky=None):
        self.fail_seq = set(fail_seq)
        self.flaky = dict(flaky or {})
        self.calls = []

    def send(self, row):
        seq = row["seq"]
        self.calls.append(seq)
        if seq in self.fail_seq:
            raise RuntimeError("boom %s" % seq)
        remaining = self.flaky.get(seq, 0)
        if remaining > 0:
            self.flaky[seq] = remaining - 1
            raise RuntimeError("flaky %s" % seq)


def make_box(clock, sender, **kwargs):
    """构造小参数的可靠中继：3 次封顶、1 秒基数退避、10 秒租约。"""
    options = dict(max_attempts=3, base_delay=1, max_delay=30,
                   lease_seconds=10, worker_id="w1")
    options.update(kwargs)
    return Outbox(MemoryStore(), sender, clock=clock, **options)


def pending_seqs(box):
    return [r["seq"] for r in box._store.pending()]


class TestBackoff(unittest.TestCase):
    def test_failed_row_not_retried_before_backoff_instant(self):
        clock = FakeClock()
        sender = ScriptedSender(flaky={1: 1})
        box = make_box(clock, sender)
        box.record("a", "x", {})

        self.assertEqual(box.relay(), 0)
        self.assertEqual(pending_seqs(box), [1])
        self.assertEqual(sender.calls, [1])

        # 退避时刻 0 + 1*2^0 = 1；不到时刻不重试。
        clock.advance(0.5)
        self.assertEqual(box.relay(), 0)
        self.assertEqual(sender.calls, [1])

        clock.advance(0.5)                 # t=1，恰好到退避时刻
        self.assertEqual(box.relay(), 1)
        self.assertEqual(sender.calls, [1, 1])

    def test_backoff_doubles_each_failure(self):
        clock = FakeClock()
        sender = ScriptedSender(flaky={1: 2})
        box = make_box(clock, sender)
        box.record("a", "x", {})

        box.relay()                       # t=0 第 1 次失败，not_before=1
        self.assertEqual(box._store.get(1)["not_before"], 1)
        clock.advance(1)
        box.relay()                       # t=1 第 2 次失败，not_before=3
        self.assertEqual(box._store.get(1)["not_before"], 3)
        clock.advance(2)
        delivered = box.relay()           # t=3 第 3 次成功
        self.assertEqual(delivered, 1)
        self.assertEqual(sender.calls, [1, 1, 1])

    def test_max_delay_caps_backoff(self):
        clock = FakeClock()
        sender = ScriptedSender(fail_seq=[1])
        box = make_box(clock, sender, max_attempts=10,
                       base_delay=1, max_delay=3)
        box.record("a", "x", {})
        box.relay()
        self.assertEqual(box._store.get(1)["not_before"], 1)
        clock.advance(1)
        box.relay()
        self.assertEqual(box._store.get(1)["not_before"], 3)
        clock.advance(2)
        box.relay()
        self.assertEqual(box._store.get(1)["not_before"], 6)
        clock.advance(3)
        box.relay()
        self.assertEqual(box._store.get(1)["not_before"], 9)


class TestDeadLetter(unittest.TestCase):
    def test_row_goes_dead_after_max_attempts(self):
        clock = FakeClock()
        sender = ScriptedSender(fail_seq=[1])
        box = make_box(clock, sender)
        box.record("a", "x", {})

        for t, attempts in ((0, 1), (1, 2), (3, 3)):
            clock.now = t
            self.assertEqual(box.relay(), 0)
            self.assertEqual(box._store.get(1)["attempts"], attempts)

        self.assertEqual(box._store.get(1)["status"], STATUS_DEAD)
        self.assertEqual(pending_seqs(box), [])
        self.assertEqual([r["seq"] for r in box._store.dead()], [1])

        # 进死信后中继不再碰它。
        clock.advance(100)
        self.assertEqual(box.relay(), 0)
        self.assertEqual(sender.calls, [1, 1, 1])

    def test_dead_head_does_not_block_later_same_aggregate(self):
        clock = FakeClock()
        sender = ScriptedSender(fail_seq=[1])
        box = make_box(clock, sender)
        box.record("a", "old", {})
        box.record("a", "new", {})

        clock.now = 0
        box.relay()
        clock.now = 1
        box.relay()
        clock.now = 3
        delivered = box.relay()          # seq 1 进死信，seq 2 当场投递
        self.assertEqual(delivered, 1)
        self.assertEqual(box._store.get(2)["status"], "sent")
        self.assertEqual(sender.calls, [1, 1, 1, 2])

    def test_backing_off_head_does_not_block_other_aggregates(self):
        clock = FakeClock()
        sender = ScriptedSender(fail_seq=[1])
        box = make_box(clock, sender)
        box.record("a", "blocked", {})
        box.record("b", "free", {})

        self.assertEqual(box.relay(), 1)
        self.assertEqual(sender.calls, [1, 2])
        self.assertEqual(box._store.get(2)["status"], "sent")
        self.assertEqual(box._store.get(1)["status"], "pending")


class TestLease(unittest.TestCase):
    def test_concurrent_relays_do_not_deliver_same_row(self):
        clock = FakeClock()
        sender = ScriptedSender()
        store = MemoryStore()

        def box(worker):
            return Outbox(store, sender, clock=clock, max_attempts=3,
                          base_delay=1, lease_seconds=10, worker_id=worker)

        store.append("a", "x", {})
        barrier = threading.Barrier(2)

        def relay(worker):
            worker_box = box(worker)
            barrier.wait()
            worker_box.relay()

        t1 = threading.Thread(target=relay, args=("w1",))
        t2 = threading.Thread(target=relay, args=("w2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(sender.calls, [1])
        self.assertEqual(store.get(1)["status"], "sent")
        self.assertIsNone(store.get(1)["lease_owner"])

    def test_lease_claim_is_mutually_exclusive(self):
        clock = FakeClock()
        store = MemoryStore()
        store.append("a", "x", {})
        box1 = Outbox(store, ScriptedSender(), clock=clock,
                      lease_seconds=10, worker_id="w1")
        box2 = Outbox(store, ScriptedSender(), clock=clock,
                      lease_seconds=10, worker_id="w2")

        self.assertTrue(store.claim(1, "w1", clock(), 10))
        self.assertFalse(store.claim(1, "w2", clock(), 10))

        # 持租约的中继照常投递，抢不到的中继空转。
        self.assertEqual(box1.relay(), 1)
        self.assertEqual(box2.relay(), 0)

    def test_expired_lease_can_be_taken_over(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptedSender()
        store.append("a", "x", {})
        box1 = Outbox(store, sender, clock=clock, lease_seconds=10,
                      worker_id="w1")
        box2 = Outbox(store, sender, clock=clock, lease_seconds=10,
                      worker_id="w2")

        self.assertTrue(store.claim(1, "w1", clock(), 10))
        clock.advance(10)                  # 到期（lease_until <= now）
        self.assertTrue(store.claim(1, "w2", clock(), 10))
        self.assertEqual(box2.relay(), 1)
        # 旧持有者无法再标记这一行，重复投递不会落账。
        self.assertFalse(store.mark_sent(1, owner="w1"))
        self.assertEqual(store.get(1)["status"], "sent")


class TestOrdering(unittest.TestCase):
    def test_same_aggregate_delivered_strictly_in_seq_order(self):
        clock = FakeClock()
        # seq 1 失败两次后恢复；seq 2/3 必须等到 seq 1 成功。
        sender = ScriptedSender(flaky={1: 2})
        box = make_box(clock, sender)
        box.record("a", "first", {})
        box.record("a", "second", {})
        box.record("a", "third", {})

        clock.now = 0
        box.relay()                        # 只有 seq 1 被尝试
        clock.now = 1
        box.relay()                        # seq 1 第二次失败
        clock.now = 3
        delivered = box.relay()            # seq 1 成功，2、3 当场跟进
        self.assertEqual(delivered, 3)
        self.assertEqual(sender.calls, [1, 1, 1, 2, 3])

    def test_later_row_cannot_jump_during_backoff(self):
        clock = FakeClock()
        sender = ScriptedSender(fail_seq=[1])
        box = make_box(clock, sender, max_attempts=5)
        box.record("a", "old", {})
        box.record("a", "new", {})

        for t in (0, 1, 3):
            clock.now = t
            self.assertEqual(box.relay(), 0)
        self.assertEqual(sender.calls, [1, 1, 1])
        self.assertEqual(box._store.get(2)["status"], "pending")

    def test_global_scan_follows_seq_across_aggregates(self):
        clock = FakeClock()
        sender = ScriptedSender()
        box = make_box(clock, sender)
        box.record("a", "1", {})
        box.record("b", "2", {})
        box.record("a", "3", {})
        box.record("b", "4", {})
        self.assertEqual(box.relay(), 4)
        self.assertEqual(sender.calls, [1, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
