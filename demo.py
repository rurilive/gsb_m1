"""cuckoof 现状演示。

第一段：NaiveSet 加键、查键、删键，看精确命中与统计。
第二段：预留的布谷鸟过滤器演示位子（见文末注释）。
"""

from cuckoof import NaiveSet


def main():
    print("=== 朴素集合 ===")
    s = NaiveSet(capacity=1024)
    for i in range(5):
        s.add("item-%d" % i)
    print("  已加 item0 命中:", "item-0" in s)
    print("  未加 never 命中:", "never" in s)
    print("  删除 item2:", s.remove("item-2"))
    print("  删除后 item2 命中:", "item-2" in s)
    print("  stats:", s.stats())

    # TODO(布谷鸟过滤器): CuckooFilter 就位后在这里补一段演示：
    # 插入若干键后查命中、量一遍未插入键的假阳性率；
    # 删一个确实在的键看它不再命中、删不存在的键拿回 False；
    # 一直插到触发扩容，打印扩容次数，并确认原有键扩容后仍全部命中。


if __name__ == "__main__":
    main()
