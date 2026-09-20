"""dedupq 现状演示：去重提交、FIFO 消费、TTL 过期后重新放行。"""

from dedupq import DedupQueue, FakeClock


def section(title):
    print(f"=== {title} ===")


def main():
    clock = FakeClock(start=1000.0)
    q = DedupQueue(ttl=5.0, clock=clock)

    section("连续提交，重复 id 丢弃")
    for msg_id in ["m1", "m2", "m1", "m3", "m2"]:
        ok = q.submit(msg_id, {"body": msg_id})
        print(f"  submit({msg_id}) -> {ok}")
    print(f"  队列长度 = {q.size()}")

    section("peek 只看不消费")
    print(f"  peek -> {q.peek()}")
    print(f"  长度仍为 {q.size()}")

    section("FIFO 消费")
    while True:
        item = q.pop()
        if item is None:
            break
        print(f"  pop -> {item}")
    print(f"  消费完长度 = {q.size()}")

    section("TTL 过期后同一 id 重新放行")
    q.submit("m9", {"body": 9})
    q.pop()
    clock.advance(6.0)
    print(f"  过期后 submit(m9) -> {q.submit('m9', {'body': 9})}")


if __name__ == "__main__":
    main()
