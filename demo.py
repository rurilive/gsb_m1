"""hitcount 现状演示。

第一段：用朴素全量计数器记几笔，看精确计数、总量、种类数与前 k。
第二段：预留的有界重频与误差演示位子（见文末注释）。
"""

from hitcount import NaiveCounter


def main():
    print("=== 朴素全量计数（现有能力） ===")
    counter = NaiveCounter()
    counter.add("alpha", 5)
    counter.add("beta", 3)
    counter.add("gamma")
    for _ in range(4):
        counter.add("beta")
    print("  alpha ->", counter.estimate("alpha"))
    print("  beta  ->", counter.estimate("beta"))
    print("  gamma ->", counter.estimate("gamma"))
    print("  total ->", counter.total())
    print("  distinct ->", counter.distinct())
    print("  top_k(2) ->", counter.top_k(2))
    counter.reset()
    print("  reset 之后 total ->", counter.total(), " distinct ->", counter.distinct())

    # TODO(有界重频与误差上界): 有界重频结构就位后在这里补一段演示：
    # 构造一个固定桶数、给定误差上界的重频估计器（如 Count-Min 加候选表
    # 或 Misra-Gries），往里面灌一批元素，其中少数是真实重频、其余是
    # 长尾偶发；打印 top_k 的估计频次与误差上界，确认真实重频一个不漏；
    # 打印 estimate 相对真实计数的偏差不超过配置上界；
    # 推进注入时钟越过时间窗，打印窗口内的重频随老样本淘汰的变化；
    # 再用两个同构结构 merge 一次，确认合并后估计不劣化。


if __name__ == "__main__":
    main()