"""knapsackdp: 纯标准库的背包问题小工具。

当前只提供一份朴素实现 NaiveKnapsack，是背包动态规划改造前的基线。
纯标准库，无外部依赖。
"""

from knapsackdp.knapsack import NaiveKnapsack, KnapsackError

__all__ = ["NaiveKnapsack", "KnapsackError"]
