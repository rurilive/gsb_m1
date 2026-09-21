"""eventwire 现状演示。

第一段：层级主题的模式匹配。
第二段：Journal 追加与读回，含末尾残行。
第三段：SyncBus 的顺序同步分发，以及慢订阅者拖住全局。
第四段：OrderedBus 的顺序编号、重放、背压与重启续号。
"""

import os
import tempfile
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
        print("=== OrderedBus 顺序编号、重放与背压 ===")
        ordered_path = os.path.join(tmp, "ordered.jsonl")
        ordered = OrderedBus(ordered_path, window=4, backlog=4,
                             overflow="drop")
        oseen = {}
        ordered.subscribe("fast", make_handler(oseen, "fast"))
        ordered.subscribe("slow", make_handler(oseen, "slow", delay=0.05))
        seqs = [ordered.publish("order.paid", {"id": n}) for n in range(1, 4)]
        print(f"  连发 3 条，拿到编号 {seqs}，逐条落盘")
        again = ordered.publish("order.paid", {"id": 2}, seq=2)
        with Journal(ordered_path) as check:
            print(f"  上游重投 2 号，返回 {again}，日志仍 "
                  f"{len(check.read())} 条，重投被幂等丢掉")

        late = {}
        ordered.subscribe("late", make_handler(late, "late"), since=1)
        print(f"  新订阅者从 1 号之后补发，subscribe 返回时已收到 "
              f"{len(late['late'])} 条")

        for n in range(4, 9):
            ordered.publish("order.paid", {"id": n})
            time.sleep(0.005)  # fast 跟得上，slow 每条 50ms 越落越多
        try:
            ordered.subscribe("ancient", make_handler({}, "ancient"), since=2)
        except WindowExpired:
            print(f"  窗口下限已到 {ordered.stats()['window_low']}，"
                  f"从 3 号补发被 WindowExpired 拒掉，不静默跳过")
        ordered.flush(timeout=5)
        print("  slow 慢只积压自己，超限按 drop 丢掉并计数：")
        for name, info in ordered.stats()["subscribers"].items():
            print(f"    {name}: 投递 {info['delivered']} "
                  f"丢弃 {info['dropped']} 状态 {info['state']}")
        ordered.close()

        reopened = OrderedBus(ordered_path)
        nxt = reopened.publish("order.paid", {"id": 9})
        print(f"  重启后水位 {reopened.stats()['high_water'] - 1}，"
              f"再发一条拿到编号 {nxt}，不重发不跳号")
        reopened.close()


if __name__ == "__main__":
    main()
