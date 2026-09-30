"""inclx：整数集合的朴素计数工具包。

当前只提供一套逐个枚举判定的朴素实现 Counting，是容斥与莫比乌斯反演改造
前的基线：判断某个数能否被给定素数集合中任意一个整除时，总是从一到上界
逐个取数，再逐个素数去试除。
纯标准库，无外部依赖，不引入第三方。
"""

from inclx.counting import Counting, CountingError

__all__ = ["Counting", "CountingError"]
