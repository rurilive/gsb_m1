"""Outbox 现状演示。

第一段：record() 落库 + relay() 逐条投递，看 seq 与状态流转。
第二段：注入假时钟和会间歇失败的 sender，演示失败按指数退避重试、
连续失败到上限进死信且不拖累后面条目，同一聚合键严格按记录序投递；
末尾演示并发中继的分区租约互斥。全程不 sleep，只拨时钟。
"""

from outboxd.outbox import MemoryStore, Outbox


class PrintSender:
    """把每条事件打到 stdout，够演示用。"""

    def send(self, row):
        print("  投递 seq=%s aggregate=%s kind=%s payload=%s"
              % (row["seq"], row["aggregate"], row["kind"], row["payload"]))


class FakeClock:
    """可手动拨动的假时钟，演示退避时刻用，绝不 sleep。"""

    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


class FlakySender:
    """按 seq 脚本失败的 sender，并打印每次投递的时刻。

    flaky 里的 seq 先失败指定次数再恢复；dead 里的 seq 永远失败。
    """

    def __init__(self, clock, flaky, dead):
        self._clock = clock
        self._flaky = dict(flaky)
        self._dead = set(dead)

    def send(self, row):
        seq = row["seq"]
        print("  t=%s 投递 seq=%s aggregate=%s kind=%s"
              % (self._clock(), seq, row["aggregate"], row["kind"]))
        if seq in self._dead:
            raise RuntimeError("对方拒收 seq=%s" % seq)
        left = self._flaky.get(seq, 0)
        if left > 0:
            self._flaky[seq] = left - 1
            raise RuntimeError("暂时失败 seq=%s（剩 %d 次）" % (seq, left - 1))


def main():
    print("=== 落库与投递 ===")
    store = MemoryStore()
    box = Outbox(store, PrintSender())
    box.record("order-1", "created", {"id": 1})
    box.record("order-1", "paid", {"id": 1})
    box.record("order-2", "created", {"id": 2})
    delivered = box.relay()
    print("  本次投递 %d 条，剩余待发 %d 条" % (delivered, len(store.pending())))
    for row in store.rows():
        print("  seq=%s status=%s" % (row["seq"], row["status"]))

    print()
    print("=== 可靠投递：退避 / 死信 / 聚合键内顺序 ===")
    clock = FakeClock()
    store = MemoryStore()
    # 4 次封顶，退避 1s、2s、4s；租约 30s。
    box = Outbox(store, FlakySender(clock, flaky={1: 2}, dead={2}),
                 clock=clock, max_attempts=4, base_delay=1, max_delay=30,
                 lease_seconds=30, worker_id="relay-A")
    box.record("order-1", "created", {"id": 1})   # seq1 失败两次后恢复
    box.record("order-1", "paid", {"id": 1})      # seq2 永远失败 → 死信
    box.record("order-1", "refunded", {"id": 1})  # seq3 必须在 seq2 之后
    box.record("order-2", "created", {"id": 2})   # seq4 另一聚合键，不等

    # 逐拍拨时钟：每拍跑一轮 relay，没进展就拨到最近的退避时刻。
    for step in range(8):
        delivered = box.relay()
        pending = store.pending()
        print("  t=%s 本轮成功 %d 条，待发 %s 死信 %s"
              % (clock(), delivered,
                 [r["seq"] for r in pending],
                 [r["seq"] for r in store.dead()]))
        if not pending:
            break
        due = min(r["not_before"] for r in pending
                  if r["not_before"] is not None)
        if due <= clock():
            clock.now += 1
        else:
            clock.now = due
    for row in store.rows():
        print("  seq=%s aggregate=%s status=%s attempts=%s"
              % (row["seq"], row["aggregate"], row["status"],
                 row["attempts"]))

    print()
    print("=== 租约互斥：两个中继抢同一分区 ===")
    clock = FakeClock()
    store = MemoryStore()
    store.append("order-9", "created", {"id": 9})
    relay_a = Outbox(store, PrintSender(), clock=clock,
                     lease_seconds=30, worker_id="relay-A")
    relay_b = Outbox(store, PrintSender(), clock=clock,
                     lease_seconds=30, worker_id="relay-B")
    print("  A 先认领 seq=1：%s" % store.claim(1, "relay-A", clock(), 30))
    print("  B 同时认领 seq=1：%s" % store.claim(1, "relay-B", clock(), 30))
    print("  B 跑一轮（抢不到，空转）成功 %d 条" % relay_b.relay())
    print("  A 跑一轮成功 %d 条" % relay_a.relay())


if __name__ == "__main__":
    main()
