"""bloomchain 现状演示。

第一段：NaiveBloomFilter 加键、查键，看最优参数与命中情况。
第二段：预留的分层扩展与基数估计演示位子（见文末注释）。
"""

from bloomchain import NaiveBloomFilter, optimal_params


def main():
    print("=== 定长布隆过滤器 ===")
    bf = NaiveBloomFilter(capacity=1000, fp_rate=0.01)
    for i in range(5):
        bf.add("event-%d" % i)
    print("  已加 event0 命中:", "event-0" in bf)
    print("  未加 event-never 命中:", "event-never" in bf)
    print("  stats:", bf.stats())

    num_bits, num_hashes = optimal_params(1000, 0.01)
    print("  期望 1000 个、误判率 0.01：位数 %d，哈希次数 %d" % (num_bits, num_hashes))

    # TODO(分层扩展与基数估计): ScalableBloomFilter 就位后在这里补一段演示：
    # 构造一个可扩展过滤器，持续加键直到自动追加新层，打印层数；
    # 确认所有已加键全部命中（无假阴性）、误判率估计是浮点；
    # 用 estimate_cardinality 估一下已插入个数，与真实数量对个量级；
    # 两个同 seed 的实例 to_bytes 逐字节一致。


if __name__ == "__main__":
    main()
