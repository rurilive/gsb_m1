"""prefixkit 现状演示。

第一段：朴素实现——对每个前缀枚举所有真前缀、逐字符比对求最长者得到前缀函数，
再据此给出单模式查找的全部起始位置、最短循环节与周期判定、各前缀出现次数汇总。
第二段：预留的线性扫描（借助已求前缀函数递推）演示位子（见文末注释）。
"""

from prefixkit import PrefixKit


def main():
    print("=== 朴素逐前缀枚举求前缀函数结果 ===")
    kit = PrefixKit("aabaabaa")
    print(f"  模式 -> {kit.pattern()}")
    print(f"  前缀函数 -> {kit.prefix_function()}")
    print(f"  第5个前缀的值 -> {kit.prefix_value(5)}")
    print(f"  逐前缀枚举比较次数 -> {kit.prefix_steps()}")
    print(f"  在文本中的全部起始位置 -> {kit.find_occurrences('aabaabaabaab')}")
    print(f"  出现次数 -> {kit.count_occurrences('aabaabaabaab')}")
    print(f"  暴力比对比较次数 -> {kit.search_steps()}")
    print(f"  各前缀出现次数 -> {kit.count_prefix_occurrences()}")
    print(f"  周期判定 -> {kit.period_info()}")
    print(f"  最短循环节 -> {kit.min_period()}")

    # TODO: 第二段演示（实现后补）
    # 以一次线性扫描、借助已经求出的前缀函数值递推，得到每个位置的前缀函数值，
    # 并据此支撑单模式查找的全部起始位置、最短循环节与周期判定、各前缀出现次数
    # 汇总等能力。实现后在这里加一段演示：用同一批字符串跑线性路径，打印每个位置
    # 的前缀函数值、查找位置、周期信息与前缀出现次数，并与上面的朴素结果逐项对照，
    # 同时暴露逐前缀枚举与线性递推的字符比较次数差距。


if __name__ == "__main__":
    main()
