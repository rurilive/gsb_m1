"""RateStore 现状演示。

第一段：朴素累加器的按维度计数、求和与求平均、合并。
第二段：预留的滑动窗口分位数演示位子（见文末注释）。
"""

from ratestore.store import RateStore


def main():
    print("=== 朴素累加器（现有能力） ===")
    s = RateStore()
    for value in (12.0, 30.0, 18.0, 24.0):
        s.record(value, label="api")
    s.record(500.0, label="db")
    print("  api 个数 =", s.count("api"))
    print("  api 总和 =", s.sum("api"))
    print("  api 平均 =", s.mean("api"))
    print("  db  个数 =", s.count("db"))
    print("  维度列表 =", s.labels())

    print("=== 合并两份累加器 ===")
    other = RateStore()
    other.record(6.0, label="api")
    s.merge(other)
    print("  合并后 api 个数 =", s.count("api"))
    print("  合并后 api 总和 =", s.sum("api"))

    # TODO(滑动窗口分位数直方图): 桶边界与指数桶、窗口内过期淘汰、
    # 桶内插值分位数、多标签查询与聚合、并发安全与时钟回拨防护
    # 全部就位后，在这里补一段演示：
    # 注入可推进的假时钟，连续 record 一批指标值，推进时钟越过 window，
    # 打印窗口内 count、sum、mean 与若干 q 的分位数随手时间的变化，
    # 以及过期样本被淘汰后桶计数仍然有界、不同 label 的维度互不干扰。


if __name__ == "__main__":
    main()
