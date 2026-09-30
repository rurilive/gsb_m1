"""spanx 现状演示。

第一段：朴素双向扫描——每个位置向左向右各看一遍，求左右第一个更大或更小元素，
并据此给出每日温度、以最小值为界的最大区间长度、柱状图边界与最大矩形面积。
第二段：预留的单调栈与逐项对照演示的位子（见文末注释）。
"""

from spanx import (
    count_naive_visits,
    daily_temperatures,
    greater_bounds,
    histogram_bounds,
    largest_rectangle,
    min_range_lengths,
    smaller_bounds,
)


def main():
    data = [3, 1, 4, 1, 5, 9, 2, 6]

    print("=== 朴素双向扫描：左右第一个更大与更小 ===")
    greater_left, greater_right = greater_bounds(data)
    smaller_left, smaller_right = smaller_bounds(data)
    print(f"  数据               {data}")
    print(f"  左侧第一个更大下标 {greater_left}")
    print(f"  右侧第一个更大下标 {greater_right}")
    print(f"  左侧第一个更小下标 {smaller_left}")
    print(f"  右侧第一个更小下标 {smaller_right}")

    print("=== 朴素派生量 ===")
    print(f"  每日温度间隔           {daily_temperatures(data)}")
    print(f"  以最小值为界的区间长度 {min_range_lengths(data)}")
    hist_left, hist_right = histogram_bounds(data)
    print(f"  柱状图左边界           {hist_left}")
    print(f"  柱状图右边界           {hist_right}")
    print(f"  柱状图最大矩形面积     {largest_rectangle(data)}")
    print(f"  本轮双向扫描比较次数   {count_naive_visits(data)}")

    # TODO: 第二段演示（实现后补）
    # 补上单调栈一次遍历求四类左右边界、每日温度、以最小值为界的最大区间长度、
    # 柱状图边界与最大矩形面积，并用稀疏表加二分独立求一遍做对照，两路与上面这条
    # 朴素路对同一批序列逐项比对；再打印双向扫描次数与栈总进栈出栈次数的规模差距，
    # 以及空序列、单元素、全相等、严格递增、严格递减、含负值等边界上的结果。


if __name__ == "__main__":
    main()
