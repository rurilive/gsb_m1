"""crawlkit 现状演示。

第一段：布隆过滤器加键、查键，看统计。
第二段：DedupStore 门面走一遍标记与判重，顺带认一遍落盘读回。
第三段：布谷鸟过滤器，可删除的后端，retry 真撤与扩容、落盘读回。
"""

from crawlkit import BloomFilter, CuckooFilter, DedupStore
from crawlkit.hashing import fingerprint, hash_pair


def _same_fingerprint_pair(fp_bits):
    """现场找两个指纹相同的不同键，演示同指纹互不拖累。"""
    base = "https://example.com/fp-base"
    want = fingerprint(hash_pair(base)[1], fp_bits)
    i = 0
    while True:
        other = "https://example.com/fp-other-%d" % i
        if fingerprint(hash_pair(other)[1], fp_bits) == want:
            return base, other
        i += 1


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

    print("=== CuckooFilter ===")
    cf = CuckooFilter(capacity=1000, fp_bits=12)
    for i in range(5):
        cf.add("https://example.com/page%d" % i)
    print("  已加 page0 命中:", "https://example.com/page0" in cf)
    cf.remove("https://example.com/page0")
    print("  remove 后 page0 命中:", "https://example.com/page0" in cf)
    print("  同批 page1 照常命中:", "https://example.com/page1" in cf)

    fp_a, fp_b = _same_fingerprint_pair(12)
    cf.add(fp_a)
    cf.add(fp_b)
    cf.remove(fp_a)
    print("  同指纹键撤一个，另一个仍命中:", fp_b in cf)

    small = CuckooFilter(capacity=8, fp_bits=12)
    keys = ["https://example.com/grow-%d" % i for i in range(200)]
    for k in keys:
        small.add(k)
    print("  踢出链触发扩容: num_buckets 8 -> %d, 200 键全部命中: %s" % (
        small.num_buckets, all(k in small for k in keys)))

    blob = cf.to_bytes()
    back = CuckooFilter.from_bytes(blob)
    print("  落盘 %d 字节，读回后 page1 命中: %s, page0 仍不在: %s" % (
        len(blob), "https://example.com/page1" in back,
        "https://example.com/page0" not in back))
    print("  stats:", cf.stats())

    print("=== DedupStore(backend='cuckoo') ===")
    store = DedupStore(capacity=1000, backend="cuckoo")
    store.mark("https://example.com/a")
    print("  is_duplicate(a):", store.is_duplicate("https://example.com/a"))
    store.retry("https://example.com/a")
    print("  retry 后 is_duplicate(a):", store.is_duplicate("https://example.com/a"))
    store.mark("https://example.com/c")
    blob = store.to_bytes()
    back = DedupStore.from_bytes(blob)
    print("  落盘读回后 is_duplicate(c): %s, a 仍不在: %s" % (
        back.is_duplicate("https://example.com/c"),
        not back.is_duplicate("https://example.com/a")))
    print("  stats:", store.stats())


if __name__ == "__main__":
    main()
