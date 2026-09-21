"""Outbox 演示。

第一段：record() 落库 + relay() 逐条投递，看 seq 与状态流转。
第二段：可靠投递——注入假时钟与间歇失败的 sender，看退避重试、
死信与同一聚合键的严格有序投递。
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
    clock = FakeClock()
    store = MemoryStore()
    # seq=1 前两次投递失败，seq=3 永远被拒收
    sender = FlakySender(flaky={1: 2}, reject={3})
    box = Outbox(store, sender, clock=clock,
                 max_attempts=3, backoff_base=5.0, backoff_factor=2.0)
    box.record("order-1", "created", {"id": 1})
    box.record("order-1", "paid", {"id": 1})
    box.record("order-2", "created", {"id": 2})

    for round_no, at in ((1, 0.0), (2, 5.0), (3, 15.0)):
        clock.advance(at - clock())
        delivered = box.relay()
        print("  t=%-5.1f 第 %d 轮：投递 %d 条，待发 %d 条，死信 %d 条"
              % (clock(), round_no, delivered,
                 len(store.pending()), len(store.dead())))
    print("  最终状态：")
    for row in store.rows():
        print("  seq=%s aggregate=%s status=%s attempts=%s"
              % (row["seq"], row["aggregate"], row["status"],
                 row["attempts"]))
    print("  说明：seq=1 退避重试期间 seq=2 不抢先，同键严格有序；"
          "seq=3 连续失败 3 次进死信，不拖累其他聚合键。")


class FakeClock:
    """手动推进的假时钟，演示退避不需要真 sleep。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += max(0.0, dt)


class FlakySender:
    """flaky 里的 seq 先失败指定次数再放行，reject 里的永远拒收。"""

    def __init__(self, flaky=None, reject=()):
        self._flaky = dict(flaky or {})
        self._reject = set(reject)

    def send(self, row):
        seq = row["seq"]
        if seq in self._reject:
            raise RuntimeError("reject seq=%s" % seq)
        if self._flaky.get(seq, 0) > 0:
            self._flaky[seq] -= 1
            raise RuntimeError("flaky seq=%s" % seq)
        print("  投递 seq=%s aggregate=%s kind=%s payload=%s"
              % (seq, row["aggregate"], row["kind"], row["payload"]))


if __name__ == "__main__":
    main()
