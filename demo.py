"""Outbox 现状演示。

第一段：record() 落库 + relay() 逐条投递，看 seq 与状态流转。
第二段：可靠投递演示——退避重试、死信、同聚合键严格按记录序。
"""

from outboxd.outbox import MemoryStore, Outbox


class PrintSender:
    """把每条事件打到 stdout，够演示用。"""

    def send(self, row):
        print("  投递 seq=%s aggregate=%s kind=%s payload=%s"
              % (row["seq"], row["aggregate"], row["kind"], row["payload"]))


class FakeClock:
    """手动推进的假时钟：退避只做时刻判定，不真 sleep。"""

    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


class FlakySender:
    """按 seq 脚本失败：fail_times[seq] 次拒收后转为成功，并打印投递。"""

    def __init__(self, fail_times):
        self._fail_times = dict(fail_times)
        self.delivered = []

    def send(self, row):
        remaining = self._fail_times.get(row["seq"], 0)
        if remaining > 0:
            self._fail_times[row["seq"]] = remaining - 1
            raise RuntimeError("对方拒收 seq=%s" % row["seq"])
        self.delivered.append(row["seq"])
        print("  投递成功 seq=%s aggregate=%s kind=%s"
              % (row["seq"], row["aggregate"], row["kind"]))


def run_reliable_demo():
    print("=== 可靠投递（假时钟 + 退避 + 死信 + 分区顺序）===")
    clock = FakeClock()
    store = MemoryStore()
    # seq=1 偶发失败 2 次后成功；seq=2 始终失败，3 次后进死信。
    sender = FlakySender({1: 2, 2: 99})
    box = Outbox(store, sender, clock=clock,
                 max_attempts=3, backoff_base=1.0, backoff_cap=8.0,
                 lease_seconds=30.0)

    box.record("order-1", "created", {"id": 1})  # seq=1
    box.record("order-1", "paid", {"id": 1})     # seq=2（毒消息）
    box.record("order-1", "shipped", {"id": 1})  # seq=3（被前两条卡住）
    box.record("order-2", "created", {"id": 2})  # seq=4（独立分区，不受影响）

    # 用注入时钟只做时刻判定，不真 sleep：每轮先中继，零进展才把时钟
    # 跳到最早的分区队首退避时刻，再中继并打印一次结果。
    for _ in range(20):
        delivered = box.relay()
        waiting = store.pending()
        if delivered == 0 and waiting:
            heads = {}
            for row in waiting:
                heads.setdefault(row["aggregate"], row)
            next_at = min(r["not_before"] for r in heads.values())
            if next_at <= clock.t:
                break
            print("  -- 时钟推进到 %.1f（退避）--" % next_at)
            clock.t = next_at
            delivered = box.relay()
            waiting = store.pending()
        print("  t=%.1f 本轮成功=%d 待发=%s 已按序投递=%s"
              % (clock.t, delivered,
                 [r["seq"] for r in waiting], sender.delivered))
        if not waiting:
            break

    for row in store.rows():
        print("  seq=%s aggregate=%s status=%s attempts=%s"
              % (row["seq"], row["aggregate"],
                 row["status"], row["attempts"]))
    print("  最终投递序（严格按同聚合键记录序）=%s" % sender.delivered)


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

    run_reliable_demo()


if __name__ == "__main__":
    main()
