"""Counting 现状演示。

第一段：朴素计数能力的逐个枚举判定，展示不超过上界且不被一组素数整除的
个数、区间内与一组数互素的个数、多个集合的并集大小、多重条件的计数。
第二段：预留的容斥与莫比乌斯反演演示位子（见文末注释）。
"""

from inclx.counting import Counting


def main():
    print("=== 朴素计数（现有能力） ===")
    c = Counting()
    primes = (2, 3, 5, 7)
    limit = 100
    count = c.count_not_divisible(limit, primes)
    print("  不超过", limit, "且不能被", primes, "中任意一个整除的个数 =", count)
    print("  朴素代价：枚举", limit, "个数，每个数最多试除", len(primes), "个素数，",
          "约", limit * len(primes), "次判定")

    print("=== 区间内互素计数 ===")
    numbers = (6, 35)
    coprime = c.count_coprime_in_range(1, 30, numbers)
    print("  区间 1 到 30 内与", numbers, "全部互素的个数 =", coprime)

    print("=== 并集与多重条件 ===")
    union = c.count_union([{1, 2, 3}, {3, 4}, {5}])
    print("  若干集合的并集大小 =", union)
    multi = c.count_multi_condition(50, (lambda v: v % 2 == 1, lambda v: v % 3 == 0))
    print("  不超过 50 且同时为奇数又是 3 的倍数的个数 =", multi)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
