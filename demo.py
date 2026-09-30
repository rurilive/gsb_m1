"""diffx 现状演示。

第一段：用朴素实现做区间加、单点查询、区间求和、离线重放与二维区域加，
看基线能力与逐元素改写的改动点规模。
第二段：预留的迭代演示位子（见文末注释）。
"""

from diffx.array import DiffArray, DiffMatrix


def main():
    print("=== 朴素区间加与单点查询（现有能力） ===")
    arr = DiffArray.zeros(8)
    arr.range_add(1, 4, 3)
    arr.range_add(3, 6, -1)
    print(f"  两次区间加后数组  -> {arr.to_list()}")
    print(f"  value_at(4)       -> {arr.value_at(4)}")
    print(f"  改动点计数        -> {arr.change_count()}")

    print("=== 朴素前缀和与区间求和（现有能力） ===")
    print(f"  prefix_sum(5)     -> {arr.prefix_sum(5)}")
    print(f"  range_sum(2, 6)   -> {arr.range_sum(2, 6)}")
    print(f"  改动点计数        -> {arr.change_count()}")

    print("=== 朴素离线重放（现有能力） ===")
    offline = DiffArray.zeros(8)
    print(f"  重放三条区间加    -> {offline.replay([(0, 2, 2), (2, 5, 4), (5, 7, -3)])}")
    print(f"  改动点计数        -> {offline.change_count()}")

    print("=== 朴素二维区域加（现有能力） ===")
    matrix = DiffMatrix.zeros(4, 4)
    matrix.region_add(1, 1, 2, 3, 5)
    matrix.region_add(0, 0, 3, 0, -2)
    for row in matrix.values():
        print(f"  {row}")
    print(f"  改动点计数        -> {matrix.change_count()}")

    # TODO: 第二段演示（实现后补）
    # 说明：差分与前缀和实现后，在这里补一段演示——用同一批数据跑新路径，
    # 打印冻结差分、两点改动、单点还原、区间求和与二维区域加的改动点计数，
    # 再逐项断言新路径与上面朴素路径的数组、单点值与区间和完全一致。


if __name__ == "__main__":
    main()
