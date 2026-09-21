"""dedupkit 现状演示。

第一段：精确去重计数。
第二段：分片账本，跨片重复会被重复计入。
第三段：落盘与读回。
第四段：预留的估算演示位子（见文末注释）。
"""

import os
import tempfile

from dedupkit import ExactCounter, Ledger, codec


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

    # TODO(估算改造): BucketSketch 落地后，在这里补三段演示：
    # 1) 灌进十几万随机 key，打印估算值、精确值以及两者的相对误差
    # 2) 两个分片的估算器 merge 起来，与先合数据再新建的估算器对比
    # 3) 估算器落盘再读回，看桶位与估算行为是否和没存过一样


if __name__ == "__main__":
    main()
