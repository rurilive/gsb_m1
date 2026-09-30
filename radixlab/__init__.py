"""radixlab：非比较排序的朴素实现。

现状实现全部走最直白的路子：非负整数序列直接交给内置排序；按位分组时对每个
元素反复求它某一位上的数字；求第几位用循环除十逐次取余；众数与分桶也各跑一套
逐元素的分组。规模一大就退化到依赖比较排序，但结果正确、口径固定。
"""

from radixlab.radix import NaiveRadix, RadixError, RadixInputError

__all__ = ["NaiveRadix", "RadixError", "RadixInputError"]
