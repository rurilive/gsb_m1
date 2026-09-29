"""MessageBus 现状演示。

第一段：订阅一个主题，publish 两条消息，看到订阅者依次收到；
取消订阅后再 publish 一条，看到订阅者不再收到。
第二段：预留的确认与重投演示位子（见文末注释）。
"""

from buskit.broker import MessageBus


def main():
    print("=== 内存发布订阅 ===")
    bus = MessageBus()
    seen = []
    sub = bus.subscribe("orders", lambda m: seen.append((m.seq, m.payload)))

    n1 = bus.publish("orders", {"id": 1})
    n2 = bus.publish("orders", {"id": 2})
    print(f"  发布两条，seq={n1},{n2}，订阅者收到 {seen}")

    sub.unsubscribe()
    bus.publish("orders", {"id": 3})
    print(f"  退订后再发布，订阅者仍只收到 {len(seen)} 条")

    # TODO(确认与重投): 在 buskit/broker.py 里给 MessageBus 加上确认、未确认重投、
    # 订阅过滤、背压与回放后，在这里加一段演示：投递后不 ack 会被重投直至死信，
    # 订阅谓词过滤掉不合意的消息，队列满了 produce 的处置，以及按 up_to_seq 回放。


if __name__ == "__main__":
    main()