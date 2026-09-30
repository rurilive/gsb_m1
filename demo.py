"""divblock 现状演示。

第一段：一组小上界走一遍现有朴素能力，看某数论函数的区间前缀和、各数约数个
数之和、与某数互素的计数之和、按商跳跃求和的枚举规模，顺带看约数个数最多的
那个数、莫比乌斯表与小范围函数表，以及非法输入的诊断。
第二段：预留的整除分块与独立印证路径的演示位子。
"""

from divblock import (
    GcdSumError,
    best_divisor_number_count,
    best_divisor_number_upto,
    coprime_count_upto,
    divisor_count_upto,
    gcd,
    mobius_prefix_upto,
    mobius_sieve,
    naive_pair_count,
    naive_scan_count,
    range_mobius_sum,
    range_totient_sum,
    totient_prefix_upto,
    totient_sieve,
)


def main():
    n = 20

    print("=== 数论求和的朴素逐个枚举 ===")
    print("  上界 n =", n, " 与 k =", 6)

    print("  欧拉函数区间和 [5, 20]:", range_totient_sum(5, n))
    print("  欧拉函数前缀和 (0..20):", totient_prefix_upto(n))
    print("  莫比乌斯区间和 [5, 20]:", range_mobius_sum(5, n))
    print("  莫比乌斯前缀和 (0..20):", mobius_prefix_upto(n))

    print("  各数约数个数之和 (0..20):", divisor_count_upto(n))

    print("  与 6 互素的个数之和 (0..20):", coprime_count_upto(n, 6))
    print("  与 1 互素的个数之和 (0..20):", coprime_count_upto(n, 1))
    print("  与 20 互素的个数之和 (0..20):", coprime_count_upto(n, 20))

    print("  约数个数最多者的约数个数 (0..20):", best_divisor_number_count(n))
    print("  约数个数最多且最小的那个数 (0..20):", best_divisor_number_upto(n))

    print("  枚举项数量级:", naive_scan_count(n))
    print("  配对枚举量级:", naive_pair_count(n))

    print("  欧拉函数表 1..10:", totient_sieve(10)[1:])
    print("  莫比乌斯表 1..10:", mobius_sieve(10)[1:])
    print("  最大公约数:", gcd(84, 36))

    print("  区间退化 [7, 4]:", range_totient_sum(7, 4))
    print("  上界为零:", range_mobius_sum(0, 0), divisor_count_upto(0))

    for bad in (-1, True):
        try:
            divisor_count_upto(bad)
        except GcdSumError as exc:
            print("  非法输入诊断:", exc.message, " 位置:", exc.position)

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
