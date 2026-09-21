"""dedupkit 现状演示。

第一段：精确去重计数。
第二段：分片账本，跨片重复会被重复计入。
第三段：落盘与读回。
第四段：分桶估算，精度、合并与落盘。
"""

import os
import random
import tempfile

from dedupkit import BucketSketch, ExactCounter, Ledger, codec


def main():
    print("=== 精确去重计数 ===")
    counter = ExactCounter()
    events = ["u1", "u2", "u1", "u3", "u2", "u4", "u1"]
    for key in events:
        print(f"  add({key!r}) -> {counter.add(key)}")
    print(f"  {len(events)} 条事件，不同 key {counter.count()} 个")

    print()
    print("=== 分片账本 ===")
    ledger = Ledger()
    shard_events = [
        ("shard-a", "u1"),
        ("shard-b", "u1"),
        ("shard-a", "u2"),
        ("shard-b", "u3"),
    ]
    for shard, key in shard_events:
        ledger.add(shard, key)
    for name in ledger.names():
        print(f"  {name}: {ledger.count(name)} 个 key")
    print(f"  total() = {ledger.total()}，同一条 u1 在 a、b 两片各记了一次")

    print()
    print("=== 落盘与读回 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ledger.json")
        codec.save(ledger, path)
        size = os.path.getsize(path)
        back = codec.load(path)
        print(f"  写进 {path}，{size} 字节")
        print(f"  读回的分片 {back.names()}，total() = {back.total()}")

    print()
    print("=== 分桶估算 ===")
    rng = random.Random(20260922)
    keys = [f"u{rng.randrange(10**9)}" for _ in range(150000)]
    sketch = BucketSketch()
    for key in keys:
        sketch.add(key)
    exact = len(set(keys))
    estimate = sketch.count()
    print(f"  灌入 {len(keys)} 条事件，不同 key 精确值 {exact}")
    print(f"  估算值 {estimate}，相对误差 {abs(estimate - exact) / exact:.2%}")
    print(f"  估算器固定占 {len(sketch.registers())} 字节，不随 key 数增长")

    print()
    print("=== 跨片合并 ===")
    half = len(keys) // 2
    left = BucketSketch()
    right = BucketSketch()
    for key in keys[:half]:
        left.add(key)
    for key in keys[half:]:
        right.add(key)
    merged = left.merge(right)
    fresh = BucketSketch()
    for key in keys:
        fresh.add(key)
    print(f"  两片各自估算 {left.count()} + {right.count()}，合后估算 {merged.count()}")
    print(f"  与先合数据再建一致: {merged.registers() == fresh.registers()}")

    print()
    print("=== 估算器落盘 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "sketch.json")
        codec.save(merged, path)
        back = codec.load(path)
        print(f"  写进 {path}，{os.path.getsize(path)} 字节")
        print(f"  读回估算 {back.count()}，桶位一致: {back.registers() == merged.registers()}")
        again = back.merge(right)
        print(f"  读回后还能接着合，估算 {again.count()}")


if __name__ == "__main__":
    main()
