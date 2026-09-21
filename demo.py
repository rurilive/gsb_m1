"""eventwire 现状演示。

第一段：层级主题的模式匹配。
第二段：Journal 追加与读回，含末尾残行。
第三段：SyncBus 的顺序同步分发，以及慢订阅者拖住全局。
第四段：预留的顺序与重放演示位子（见文末注释）。
"""

import os
import tempfile
import time

from eventwire import Journal, SyncBus, matches

MATCH_CASES = [
    ("gateway.*", "gateway.retry"),
    ("gateway.*", "gateway.retry.done"),
    ("gateway.**", "gateway"),
    ("gateway.**", "gateway.retry.done"),
    ("order.paid", "order.paid"),
]


def make_handler(seen, name, delay=0.0):
    def handler(topic, payload):
        if delay:
            time.sleep(delay)
        seen.setdefault(name, []).append(topic)
    return handler


def main():
    print("=== 主题匹配 ===")
    for pattern, topic in MATCH_CASES:
        print(f"  {pattern} 覆盖 {topic}: {matches(pattern, topic)}")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "events.jsonl")

        print()
        print("=== Journal 追加与读回 ===")
        journal = Journal(path)
        for seq in range(1, 4):
            journal.append({"seq": seq, "topic": "order.created",
                            "payload": {"id": seq}})
        print(f"  追加 3 条，读回 {len(journal.read())} 条，"
              f"文件 {os.path.getsize(path)} 字节")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write('{"seq": 4, "topic": "order.pa')
        print(f"  尾部留了半行，读回还是 {len(journal.read())} 条")
        journal.close()

        print()
        print("=== 同步分发与慢订阅者 ===")
        bus = SyncBus()
        seen = {}
        bus.subscribe("audit", make_handler(seen, "audit"))
        bus.subscribe("archive", make_handler(seen, "archive", delay=0.05),
                      "order.**")
        bus.subscribe("alert", make_handler(seen, "alert"), "order.paid")
        started = time.perf_counter()
        for seq in range(1, 4):
            delivered = bus.publish("order.paid", {"id": seq})
            print(f"  发第 {seq} 条，投给 {delivered} 个订阅者")
        elapsed = time.perf_counter() - started
        print(f"  三条发完花了 {elapsed:.3f} 秒，慢的 archive 把发布方"
              f"和 alert 都按在原地等")
        for name in bus.subscriber_names():
            print(f"  {name} 收到: {seen.get(name, [])}")

    # TODO(顺序与重放): OrderedBus 落地后，在这里加一段演示：
    # 1) 发布拿到单调编号并落盘，同一个编号再投一次被幂等丢掉
    # 2) 新订阅者按 since 重放窗口内的历史，窗口外的老编号报过期
    # 3) 慢订阅者只让自己积压，发布方和快订阅者不受影响，
    #    积压超限后从 stats() 里读到丢弃计数或断开状态
    # 4) 关掉再打开同一个文件，编号接着水位走，不重发也不跳号


if __name__ == "__main__":
    main()
