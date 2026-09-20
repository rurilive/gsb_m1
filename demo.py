"""MemTable 现状演示。

第一段：写入落在最新一层，放不下就往下压实。
第二段：从新到旧逐层查找，新值压过旧值。
第三段：预留的布隆过滤器演示位子（见文末注释）。
"""

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

    # TODO(过滤器改造): 每层布隆过滤器实现后，在这里加一段演示：
    # 查不存在的 key 时过滤器如何让整层直接跳过，stats 里
    # 跳过次数、穿透次数、估算误判率怎么变；再演示压实后
    # 过滤器重建、以及落盘读回来的效果。


if __name__ == "__main__":
    main()
