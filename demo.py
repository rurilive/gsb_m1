"""movavg 现状演示。

第一段：用朴素全量平均记几个样本，看平均与计数怎么随样本增长。
第二段：预留的滑动窗口速率与分位演示位子（见文末注释）。
"""

from movavg.meter import Meter


def main():
    print("=== 朴素全量平均（现有能力） ===")
    m = Meter()
    for v in (1.0, 2.0, 3.0, 4.0):
        m.record(v)
    print("  count ->", m.count())
    print("  total ->", m.total())
    print("  mean  ->", m.mean())
    m.reset()
    print("  reset 之后 mean ->", m.mean(), " count ->", m.count())

    # TODO(滑动窗口速率与分位): 窗口、分位、衰减就位后，在这里加一段演示：
    # 新建一个带注入时钟的窗口仪表，压入一段时间内的事件，推进时钟越过
    # 窗口长度，打印窗口内速率与总量随淘汰变化；再记录一批延迟样本，打印
    # 分位数（桶内插值），并对比窗口内外的样本是否计入。


if __name__ == "__main__":
    main()
