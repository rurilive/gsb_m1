"""topichub 现状演示。

第一段：建库订阅一个主题，publish 几条看到回调按发布顺序依次收到，
退订后再 publish 看到回调不再收到。
第二段：预留的多主题分发、过滤、至少一次投递与确认重投的演示位子
（见文末注释）。
"""

from topichub.hub import TopicHub


def main():
    print("=== 朴素一对一回调注册 ===")
    hub = TopicHub()
    seen = []
    sub = hub.subscribe("orders", lambda m: seen.append((m.seq, m.payload)))

    n1 = hub.publish("orders", {"id": 1})
    n2 = hub.publish("orders", {"id": 2})
    print("  发布两条，seq=%d,%d，回调收到 %s" % (n1, n2, seen))
    print("  在途未确认 pending -> %d" % hub.pending())
    print("  主题 orders 活跃订阅数 -> %d" % hub.subscriber_count("orders"))

    sub.unsubscribe()
    hub.publish("orders", {"id": 3})
    print("  退订后再发布，回调仍只收到 %d 条" % len(seen))
    print("  退订后活跃订阅数 -> %d" % hub.subscriber_count("orders"))

    # TODO(多主题与至少一次投递): 在 topichub/hub.py 里给 TopicHub 加上多主题
    # 分发与通配主题、订阅谓词过滤、至少一次投递与确认（ack）、未确认消息按注入
    # 时钟超时重投并在次数封顶后进死信、同一订阅者按发布顺序投递、订阅者有界缓冲
    # 的背压策略、退订后未 ack 在途消息的处置之后，在这里加一段演示：先建一个
    # 注入时钟，订阅两个主题（其中一个是通配）各带一个谓词，publish 几条打印每个
    # 订阅者收到的主题与序号，确认过滤生效；再让某个订阅者故意不 ack，把注入时钟
    # 往前拨过超时阈值，打印这条消息被重投的次数与重投后的序号，确认未 ack 会重投、
    # 重投达到封顶后落进死信；接着把某个订阅者缓冲填满，打印满时按策略的处置结果；
    # 最后退订一个仍有未 ack 在途消息的订阅，打印这些在途消息的归宿，确认退订后
    # 不再收到新消息。


if __name__ == "__main__":
    main()
