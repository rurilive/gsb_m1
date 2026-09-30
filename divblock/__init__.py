"""divblock：数论求和的朴素工具包。

包内所有能力都用最直白的逐个枚举实现，结果精确，规模一大就慢。
"""

from .sumtools import (
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

__all__ = [
    "GcdSumError",
    "best_divisor_number_count",
    "best_divisor_number_upto",
    "coprime_count_upto",
    "divisor_count_upto",
    "gcd",
    "mobius_prefix_upto",
    "mobius_sieve",
    "naive_pair_count",
    "naive_scan_count",
    "range_mobius_sum",
    "range_totient_sum",
    "totient_prefix_upto",
    "totient_sieve",
]
