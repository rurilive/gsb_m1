"""Outbox 演示。

第一段：record() 落库 + relay() 逐条投递，看 seq 与状态流转。
第二段：可靠投递——退避重试、死信、租约互斥与聚合键保序。
"""

from outboxd.outbox import MemoryStore, Outbox


class PrintSender:
    """把每条事件打到 stdout，够演示用。"""

    def send(self, row):
        print("  投递 seq=%s aggregate=%s kind=%s payload=%s"
              % (row["seq"], row["aggregate"], row["kind"], row["payload"]))


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

    print("=== 可靠投递 ===")
    demo_reliable()


class FakeClock:
    """手动推进的假时钟，演示退避不用真 sleep。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FlakySender:
    """seq=1 永远拒收的 sender，其余正常，打印每次投递时刻。"""

    def __init__(self, clock):
        self._clock = clock

    def send(self, row):
        print("  t=%-4s 投递 seq=%s aggregate=%s"
              % (self._clock(), row["seq"], row["aggregate"]))
        if row["seq"] == 1:
            raise RuntimeError("拒收")


def demo_reliable():
    clock = FakeClock()
    store = MemoryStore()
    box = Outbox(store, FlakySender(clock), clock=clock,
                 max_attempts=3, base_backoff=1.0, owner="relay-1")
    box.record("order-1", "created", {"id": 1})
    box.record("order-1", "paid", {"id": 1})
    box.record("order-2", "created", {"id": 2})

    print("-- 首轮：seq=1 被拒，挡住 order-1 的 seq=2，order-2 不受影响")
    box.relay()
    for round_no in range(2, 4):
        clock.now = max((r["next_attempt_at"] for r in store.pending()),
                        default=clock.now)
        print("-- 第 %d 轮：时钟推进到 t=%s，退避到期再试" % (round_no, clock.now))
        box.relay()
    print("-- 终态：seq=1 连续失败 3 次进死信，seq=2 放行补投")
    for row in store.rows():
        print("  seq=%s aggregate=%s status=%s attempts=%s"
              % (row["seq"], row["aggregate"], row["status"], row["attempts"]))

    print("-- 租约：relay-2 在租约期内抢不到，到期后才能认领")
    seq = box.record("order-3", "created", {"id": 3})
    store.claim(seq, "relay-1", now=clock.now, ttl=10.0)
    contending = Outbox(store, FlakySender(clock), clock=clock, owner="relay-2")
    print("  租约期内 relay-2 投递 %d 条" % contending.relay())
    clock.now += 10.0
    print("  租约到期后 relay-2 投递 %d 条" % contending.relay())


if __name__ == "__main__":
    main()
