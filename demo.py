"""bloomx 现状演示。

第一段：布隆过滤器加键、查键，看统计与落盘读回。
第二段：RandomState 定种随机流跑一遍，认一遍可复现。
第三段：预留的计数删除与分层扩展演示位子（见文末注释）。
"""

from bloomx import BloomFilter, RandomState


def main():
    print("=== 布隆过滤器 ===")
    bf = BloomFilter(capacity=1000, fp_rate=0.01)
    for i in range(5):
        bf.add("event-%d" % i)
    print("  已加 event0 命中:", "event-0" in bf)
    print("  未加 never 命中:", "event-never" in bf)
    print("  stats:", bf.stats())
    back = BloomFilter.from_bytes(bf.to_bytes())
    print("  落盘 %d 字节，读回后 event0 命中: %s" % (len(bf.to_bytes()), "event-0" in back))

    print("=== 定种随机流 ===")
    a = RandomState(2026)
    b = RandomState(2026)
    print("  两次取流一致:", [a.getrandbits(16) for _ in range(4)] ==
          [b.getrandbits(16) for _ in range(4)])

    # TODO(计数与分层): CountingBloomFilter 与 ScalableBloomFilter 就位后在这里补两段演示：
    # 计数过滤器加键、删一个键、被删键不再命中而同位置的其他键照常命中、
    # 真删返回 True 而删不存在的键返回 False；
    # 分层过滤器加到单层满自动长层、级联查询已加键全命中（无假阴性）、
    # 误判率估计给出浮点、同 seed 两个实例逐字节一致。


if __name__ == "__main__":
    main()
