"""eventwire 现状演示。

第一段：层级主题的模式匹配。
第二段：Journal 追加与读回，含末尾残行。
第三段：SyncBus 的顺序同步分发，以及慢订阅者拖住全局。
第四段：OrderedBus 的编号落盘、重放、背压与重启续号。
"""

import os
import tempfile
import threading
import time

from eventwire import Journal, OrderedBus, SyncBus, WindowExpired, matches

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

        print()
        print("=== OrderedBus 编号、重放与背压 ===")
        ordered_path = os.path.join(tmp, "ordered.jsonl")
        bus = OrderedBus(ordered_path, window=4, backlog=2, overflow="drop")
        for seq in range(1, 7):
            assigned = bus.publish("order.paid", {"id": seq})
            print(f"  发布拿到编号 {assigned}")
        dup = bus.publish("order.paid", {"id": 3}, seq=3)
        print(f"  同号重投 {dup} 被幂等丢掉，"
              f"重复计数 {bus.stats()['duplicates']}")

        replayed = {}
        bus.subscribe("replay", make_handler(replayed, "replay"), since=4)
        bus.wait_idle()
        print(f"  since=4 补发窗口内旧事件: {replayed['replay']}")
        try:
            bus.subscribe("too-old", make_handler({}, "too-old"), since=0)
        except WindowExpired as failure:
            print(f"  since=0 已滚出窗口: {failure}")

        slow_seen = []
        release = threading.Event()

        def slow_handler(topic, payload):
            release.wait(2)
            slow_seen.append(payload["id"])

        bus.subscribe("slow", slow_handler)
        fast_seen = {}
        bus.subscribe("fast", make_handler(fast_seen, "fast"))
        started = time.perf_counter()
        for seq in range(7, 12):
            bus.publish("order.paid", {"id": seq})
        print(f"  连发 5 条只花 {time.perf_counter() - started:.3f} 秒，"
              f"慢的 slow 不拖发布方")
        release.set()
        bus.wait_idle()
        stats = bus.stats()
        print(f"  水位 {stats['watermark']}，窗口下限 {stats['window_floor']}，"
              f"slow 投 {stats['subscribers']['slow']['delivered']} "
              f"丢 {stats['subscribers']['slow']['dropped']}")
        bus.close()

        print()
        print("=== 重启续号 ===")
        bus = OrderedBus(ordered_path, window=4, backlog=2)
        print(f"  重开同一文件，下一条编号 {bus.publish('order.paid', {'id': 99})}，"
              f"不重发不跳号")
        bus.close()


if __name__ == "__main__":
    main()
