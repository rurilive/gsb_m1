"""Outbox 现状演示。

第一段：record() 落库 + relay() 逐条投递，看 seq 与状态流转。
第二段：预留的可靠投递演示位子（见文末注释）。
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

    # TODO(可靠投递改造): 中继可靠投递实现后，在这里加一段演示：
    # 注入假时钟和会间歇失败的 sender，展示失败后按退避重试、
    # 连续失败到上限进死信且不拖累后面的条目，以及同一聚合键
    # 在重试期间仍严格按记录序投递。


if __name__ == "__main__":
    main()
