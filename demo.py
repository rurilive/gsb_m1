"""MemTable 演示。

第一段：写入落在最新一层，放不下就往下压实。
第二段：从新到旧逐层查找，新值压过旧值。
第三段：每层布隆过滤器让空查整层跳过；压实后过滤器重建；
        落盘读回后行为与统计一致；写超容量后扩容把误判率压回来。
"""

import os
import tempfile

from blooms.bloom import BloomFilter
from blooms.table import MemTable


def main():
    print("=== 写入与压实 ===")
    t = MemTable(level_capacity=2, ratio=4)
    for i, k in enumerate("abcde"):
        t.put(k, i)
    for index, level in enumerate(t.levels()):
        print(f"  L{index}: {level}")
    s = t.stats()
    print(f"  stats: puts={s['puts']} levels={s['levels']}")

    print("=== 逐层查找 ===")
    t.put("a", 99)
    print(f"  get('a') -> {t.get('a')!r}   （新层压过旧层）")
    print(f"  get('b') -> {t.get('b')!r}")
    print(f"  get('zz') -> {t.get('zz')!r}")
    s = t.stats()
    print(f"  stats: gets={s['gets']} hits={s['hits']} misses={s['misses']}")

    print("=== 布隆过滤器：空查跳过整层 ===")
    t = MemTable(level_capacity=4, ratio=2, error_rate=0.01)
    for i in range(40):
        t.put(f"k{i}", i)
    print(f"  层数={t.stats()['levels']}，每层条目="
          f"{[info['items'] for info in t.filter_stats()]}")
    t.get("absent-xyz")
    s = t.stats()
    print(f"  空查一次：穿透={s['filter_probes']} 跳过={s['filter_skips']} "
          f"（层 dict 一次没扫）")
    print(f"  表级估算误判率={s['estimated_false_positive_rate']:.4%}")
    t.get("k0")
    s = t.stats()
    print(f"  再查最深层 k0：穿透累计={s['filter_probes']} 跳过累计={s['filter_skips']}")

    print("=== 压实后过滤器重建，无假阴 ===")
    for i in range(40, 70):
        t.put(f"k{i}", i)
    missing = [f"k{i}" for i in range(70) if t.get(f"k{i}") != i]
    print(f"  压实多轮后逐个核对：{len(missing)} 个键丢失（应为 0）")

    print("=== 落盘读回：行为与统计一个样 ===")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "table.json")
        t.save(path)
        loaded = MemTable.load(path)
    print(f"  stats 一致：{loaded.stats() == t.stats()}")
    print(f"  数据一致：{loaded.levels() == t.levels()}")
    print(f"  读回后空查仍跳过：get('absent-zzz') -> {loaded.get('absent-zzz')!r}")

    print("=== 写超容量：过滤器长大，误判率回落 ===")
    f = BloomFilter(20, error_rate=0.02)
    for i in range(800):
        f.add(i)
    print(f"  20 条容量塞 800 条：saturated={f.saturated} "
          f"估算误判率={f.estimated_false_positive_rate:.2%}")
    f.rebuild(range(800))
    print(f"  扩容重建后：expected_items={f.expected_items} saturated={f.saturated} "
          f"估算误判率={f.estimated_false_positive_rate:.2%}")


if __name__ == "__main__":
    main()
