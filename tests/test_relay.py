"""可靠中继的行为测试：退避、死信、租约互斥与聚合键有序投递。"""

import unittest

from outboxd.outbox import MemoryStore, Outbox


class FakeClock:
    """注入用手动时钟，relay 不 sleep，靠 advance 推进时间。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class ScriptSender:
    """按 seq 脚本失败：fail_times 控制每条还要失败几次。"""

    def __init__(self, fail_times=None):
        self.sent = []
        self.fail_times = dict(fail_times or {})

    def send(self, row):
        seq = row["seq"]
        if self.fail_times.get(seq, 0) > 0:
            self.fail_times[seq] -= 1
            raise RuntimeError("boom %s" % seq)
        self.sent.append(row)


def make_box(store, sender, clock, **kwargs):
    params = dict(max_attempts=3, backoff_base=10.0, backoff_factor=2.0,
                  backoff_cap=1000.0, lease_ttl=30.0)
    params.update(kwargs)
    return Outbox(store, sender, clock=clock, **params)


class TestBackoff(unittest.TestCase):
    def test_retry_waits_until_exact_backoff_moment(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 2})
        box = make_box(store, sender, clock)
        box.record("a", "x", {})

        box.relay()  # t=0 第 1 次失败，退避 10s
        self.assertEqual(store.get(1)["next_attempt_at"], 10.0)

        clock.advance(9.9)  # 退避未满，不重试
        self.assertEqual(box.relay(), 0)
        self.assertEqual(sender.fail_times[1], 1)

        clock.advance(0.1)  # t=10 恰好到期，第 2 次失败，退避 20s
        self.assertEqual(box.relay(), 0)
        self.assertEqual(store.get(1)["next_attempt_at"], 30.0)

        clock.advance(19.9)
        self.assertEqual(box.relay(), 0)
        clock.advance(0.1)  # t=30 到期，投递成功
        self.assertEqual(box.relay(), 1)
        self.assertEqual([r["seq"] for r in sender.sent], [1])

    def test_backoff_grows_exponentially_and_caps(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 99})
        box = make_box(store, sender, clock, max_attempts=99,
                       backoff_cap=25.0)
        box.record("a", "x", {})
        box.relay()  # 失败 1 次：+10
        self.assertEqual(store.get(1)["next_attempt_at"], 10.0)
        clock.advance(10.0)
        box.relay()  # 失败 2 次：+20
        self.assertEqual(store.get(1)["next_attempt_at"], 30.0)
        clock.advance(20.0)
        box.relay()  # 失败 3 次：+40 被 cap 截为 +25
        self.assertEqual(store.get(1)["next_attempt_at"], 55.0)

    def test_no_real_sleep_needed(self):
        # 全程用 FakeClock，若实现里真 sleep 本测试会明显变慢
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 1})
        box = make_box(store, sender, clock)
        box.record("a", "x", {})
        box.relay()
        clock.advance(10.0)
        self.assertEqual(box.relay(), 1)


class TestDeadLetter(unittest.TestCase):
    def test_reaching_max_attempts_moves_row_to_dead(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 10})
        box = make_box(store, sender, clock)  # max_attempts=3
        box.record("a", "x", {})
        box.relay()  # 失败 1
        clock.advance(10.0)
        box.relay()  # 失败 2
        self.assertEqual(store.get(1)["status"], "pending")
        clock.advance(20.0)
        box.relay()  # 失败 3，到达上限
        self.assertEqual(store.get(1)["status"], "dead")
        self.assertEqual([r["seq"] for r in store.dead()], [1])
        self.assertEqual(store.pending(), [])
        clock.advance(1000.0)  # 死信不再投递
        self.assertEqual(box.relay(), 0)

    def test_poison_row_does_not_block_other_aggregates(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 10})
        box = make_box(store, sender, clock)
        box.record("bad", "x", {})
        box.record("good", "y", {})
        self.assertEqual(box.relay(), 1)  # good 正常投递
        self.assertEqual([r["seq"] for r in sender.sent], [2])
        clock.advance(10.0)
        box.relay()
        clock.advance(20.0)
        box.relay()  # bad 进死信
        self.assertEqual(store.get(1)["status"], "dead")


class TestLease(unittest.TestCase):
    def test_lease_excludes_other_relays_until_expiry(self):
        clock = FakeClock()
        store = MemoryStore()
        sender_a = ScriptSender()
        sender_b = ScriptSender()
        box_a = make_box(store, sender_a, clock, owner="a", lease_ttl=100.0)
        box_b = make_box(store, sender_b, clock, owner="b", lease_ttl=100.0)
        box_a.record("a", "x", {})

        # a 的租约未过期时，b 认领不到，不能投递
        self.assertIsNotNone(store.claim(1, "a", clock(), 100.0))
        self.assertIsNone(store.claim(1, "b", clock(), 100.0))
        self.assertEqual(box_b.relay(), 0)
        self.assertEqual(sender_b.sent, [])

        clock.advance(100.0)  # 租约过期，b 可以认领并投递
        self.assertEqual(box_b.relay(), 1)
        self.assertEqual(len(sender_b.sent), 1)

    def test_concurrent_relays_do_not_double_deliver(self):
        clock = FakeClock()
        store = MemoryStore()
        sender_a = ScriptSender()
        sender_b = ScriptSender()
        box_a = make_box(store, sender_a, clock, owner="a")
        box_b = make_box(store, sender_b, clock, owner="b")
        box_a.record("a", "x", {})
        box_a.record("b", "y", {})
        box_a.relay()
        box_b.relay()  # 已发的不重投
        self.assertEqual(len(sender_a.sent) + len(sender_b.sent), 2)

    def test_lease_released_on_failure_so_retry_can_proceed(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 1})
        box = make_box(store, sender, clock, owner="a")
        box.record("a", "x", {})
        box.relay()  # 失败，租约当场释放，靠退避期挡重试
        self.assertIsNone(store.get(1)["lease_owner"])
        clock.advance(10.0)
        self.assertEqual(box.relay(), 1)


class TestOrdering(unittest.TestCase):
    def test_same_aggregate_delivers_in_record_order_after_retry(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 1})
        box = make_box(store, sender, clock)
        box.record("order-1", "created", {})
        box.record("order-1", "paid", {})
        box.record("order-2", "created", {})

        box.relay()  # seq1 失败，seq2 不得抢先，seq3 不受影响
        self.assertEqual([r["seq"] for r in sender.sent], [3])

        clock.advance(10.0)
        box.relay()  # 退避到期，严格按记录序补投
        self.assertEqual([r["seq"] for r in sender.sent], [3, 1, 2])

    def test_failed_head_blocks_later_events_of_same_aggregate(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 10})
        box = make_box(store, sender, clock)
        box.record("a", "first", {})
        box.record("a", "second", {})
        box.relay()
        clock.advance(10.0)
        box.relay()
        self.assertEqual(sender.sent, [])  # 头条未成功，后续一律不投
        self.assertEqual(store.get(2)["status"], "pending")

    def test_backoff_head_blocks_aggregate_until_due(self):
        clock = FakeClock()
        store = MemoryStore()
        sender = ScriptSender(fail_times={1: 1})
        box = make_box(store, sender, clock)
        box.record("a", "first", {})
        box.relay()  # seq1 失败进入退避
        box.record("a", "second", {})  # 退避期间新落库的同键事件
        self.assertEqual(box.relay(), 0)  # 退避未满，seq2 也不许抢先
        clock.advance(10.0)
        self.assertEqual(box.relay(), 2)
        self.assertEqual([r["seq"] for r in sender.sent], [1, 2])


if __name__ == "__main__":
    unittest.main()
