"""crawlkit 现状演示。

第一段：布隆过滤器加键、查键，看统计。
第二段：DedupStore 门面走一遍标记与判重，顺带认一遍落盘读回。
第三段：预留的布谷鸟过滤器演示位子（见文末注释）。
"""

from crawlkit import BloomFilter, DedupStore


def main():
    print("=== 布隆过滤器 ===")
    bf = BloomFilter(capacity=1000, fp_rate=0.01)
    for i in range(5):
        bf.add("https://example.com/page%d" % i)
    print("  已加 page0 命中:", "https://example.com/page0" in bf)
    print("  未加 never 命中:", "https://example.com/never" in bf)
    print("  stats:", bf.stats())

    print("=== DedupStore ===")
    store = DedupStore(capacity=1000)
    store.mark("https://example.com/a")
    print("  is_duplicate(a):", store.is_duplicate("https://example.com/a"))
    print("  is_duplicate(b):", store.is_duplicate("https://example.com/b"))
    blob = store.to_bytes()
    back = DedupStore.from_bytes(blob)
    print("  落盘 %d 字节，读回后 is_duplicate(a): %s" % (
        len(blob), back.is_duplicate("https://example.com/a")))
    print("  stats:", store.stats())

    # TODO(布谷鸟): CuckooFilter 就位后在这里补一段演示：
    # 加键、remove 一个键、撤掉的键不再命中而同指纹的其他键照常命中、
    # 踢出链触发扩容前后查询结果一致、落盘读回行为不变。


if __name__ == "__main__":
    main()
