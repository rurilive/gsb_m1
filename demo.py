"""booklib 现状演示。

第一段：朴素订单簿的挂单、线性求最优价、按价位累加数量与撤销。
第二段：撮合演示的占位（见文末注释）。
"""

from booklib import BUY, SELL, FlatBook


def main():
    print("=== 朴素挂单与最优价 ===")
    b = FlatBook()
    b.add(BUY, 100, 5)
    b.add(BUY, 103, 2)
    b.add(BUY, 101, 4)
    b.add(SELL, 110, 6)
    b.add(SELL, 107, 3)
    print("  最优买价:", b.best_bid())
    print("  最优卖价:", b.best_ask())
    print("  买盘在 101 的数量:", b.qty_at(BUY, 101))
    print("  当前订单总数:", len(b))

    print("=== 撤销与最优价更新 ===")
    top = b.orders(BUY)[1][0]
    print("  撤销订单号:", top, "结果:", b.cancel(top))
    print("  撤销后最优买价:", b.best_bid())
    print("  撤销不存在的订单:", b.cancel(99999))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
