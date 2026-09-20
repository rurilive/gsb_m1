"""MemTable 演示。

第一段：写入落在最新一层，放不下就往下压实。
第二段：从新到旧逐层查找，新值压过旧值。
第三段：每层布隆过滤器如何跳过空扫、压实后重建、落盘往返与自动扩容。
"""

import os
import tempfile

from blooms.table import MemTable
from blooms.bloom import BloomFilter


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

    print("=== 布隆过滤器：跳过、重建与落盘 ===")
    deep = MemTable(level_capacity=1, ratio=2, error_rate=0.01)
    for i, k in enumerate("abcd"):
        deep.put(k, i)
    print(f"  层级: {[sorted(level) for level in deep.levels()]}")
    before = deep.stats()
    print(f"  get('zz') -> {deep.get('zz')!r}   （键不存在）")
    after = deep.stats()
    print(f"  跳过 {after['bloom_skips'] - before['bloom_skips']} 层，"
          f"真扫 {after['bloom_scans'] - before['bloom_scans']} 层，"
          f"穿透={after['bloom_penetrations']}")
    print(f"  各层估算误判率: "
          f"{[round(r, 4) for r in after['bloom_level_error_rates']]}")
    print("  继续写入触发逐层压实，已写键全部还查得到 -> 重建无假阴")
    keys = [f"k{i}" for i in range(12)]
    for i, k in enumerate(keys):
        deep.put(k, i)
    print(f"  抽查: get('k11')={deep.get('k11')!r} get('a')={deep.get('a')!r}")

    tmpdir = tempfile.mkdtemp(prefix="blooms-demo-")
    try:
        path = os.path.join(tmpdir, "memtable.blm")
        deep.dump(path)
        revived = MemTable.load(path)
        print(f"  落盘读回: stats 一致 -> {revived.stats() == deep.stats()}，"
              f"get('k7')={revived.get('k7')!r}")
    finally:
        os.remove(os.path.join(tmpdir, "memtable.blm"))
        os.rmdir(tmpdir)

    flt = BloomFilter(100, 0.01)
    for i in range(100):
        flt.add(f"item-{i}")
    first = flt.estimated_false_positive_rate()
    for i in range(100, 400):
        flt.add(f"item-{i}")
    grown = flt.estimated_false_positive_rate()
    print(f"  过滤器扩容: 写满时估算误判率 {first:.4f}，"
          f"写到 4 倍后容量 {flt.expected_items}、误判率回落到 {grown:.4f}")


if __name__ == "__main__":
    main()
