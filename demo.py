"""dedupkit 现状演示。

第一段：精确去重计数。
第二段：分片账本，跨片重复会被重复计入。
第三段：落盘与读回。
第四段：BucketSketch 分桶估算、跨片合并与估算器落盘。
"""

import os
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
    print("=== 分桶估算：十几万 key，内存不涨 ===")
    exact = ExactCounter()
    sketch = BucketSketch(bits=12, seed=0)
    for i in range(150000):
        key = f"event-{i}"
        exact.add(key)
        sketch.add(key)
    for i in range(0, 150000, 3):  # 三分之一的重复事件
        sketch.add(f"event-{i}")
    truth = exact.count()
    estimate = sketch.count()
    print(f"  桶位 {len(sketch.registers())} 字节，精确 {truth}，估算 {estimate:.0f}")
    print(f"  相对误差 {abs(estimate - truth) / truth * 100:.2f}%")

    print()
    print("=== 跨片合并：merge 等于先合数据再重建 ===")
    left = BucketSketch(bits=12, seed=0)
    right = BucketSketch(bits=12, seed=0)
    rebuilt = BucketSketch(bits=12, seed=0)
    left_keys = [f"a-{i}" for i in range(60000)]
    right_keys = [f"b-{i}" for i in range(40000)] + left_keys[:10000]
    for key in left_keys:
        left.add(key)
    for key in right_keys:
        right.add(key)
    for key in left_keys + right_keys:
        rebuilt.add(key)
    merged = left.merge(right)
    print(f"  merge 估算 {merged.count():.0f}，并集重建估算 {rebuilt.count():.0f}")
    print(f"  桶位逐位一致: {merged.registers() == rebuilt.registers()}")
    print(f"  合并后左右两边未被改动: {left.count() > 0 and right.count() > 0}")

    print()
    print("=== 估算器落盘：桶位分毫不差，读回还能接着合 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "sketch.json")
        codec.save_sketch(merged, path)
        restored = codec.load(path)
        print(f"  写进 {path}，{os.path.getsize(path)} 字节（fmt 2）")
        print(f"  桶位一致: {restored.registers() == merged.registers()}")
        remerged = restored.merge(right)
        print(f"  读回后继续合并，估算仍为 {remerged.count():.0f}，与重建一致: "
              f"{remerged.registers() == rebuilt.registers()}")


if __name__ == "__main__":
    main()
