"""背包问题的朴素实现（改造前基线）。

只提供一条最直白的递归枚举路径：对每个物品依次决定取或不取，
逐条累加重量判断是否超限，结果正确，但代价随物品个数指数级上涨。
没有任何动态规划、没有零一与完全背包的口径区分，也没有恰好装满的说法。
纯标准库，无外部依赖。
"""


class KnapsackError(Exception):
    """背包参数错误的基类，继承自 Exception。"""


class NaiveKnapsack:
    """朴素背包：持有物品的重量与价值列表以及背包容量的上限。

    重量与价值一一对应，价值为非负数。价值为零的物品仍然算一件可选之物。
    """

    def __init__(self, weights, values, capacity):
        weights = list(weights)
        values = list(values)
        if len(weights) != len(values):
            raise KnapsackError("weights and values length mismatch")
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise KnapsackError("capacity must be an int")
        if capacity < 0:
            raise KnapsackError("capacity must not be negative")
        for w in weights:
            if not isinstance(w, int) or isinstance(w, bool):
                raise KnapsackError("weight must be an int")
            if w < 0:
                raise KnapsackError("weight must not be negative")
        for v in values:
            if not isinstance(v, int) or isinstance(v, bool):
                raise KnapsackError("value must be an int")
            if v < 0:
                raise KnapsackError("value must not be negative")
        self._weights = weights
        self._values = values
        self._capacity = capacity

    def __len__(self):
        return len(self._weights)

    @property
    def capacity(self):
        return self._capacity

    def max_value(self):
        """递归枚举每个物品取或不取，逐条累加重量判超限，返回最大总价值。"""
        return self._enumerate(0, 0, 0)

    def _enumerate(self, index, used, value):
        if index == len(self._weights):
            return value
        # 不取当前物品
        best = self._enumerate(index + 1, used, value)
        # 取当前物品，只有在重量不超限时才继续
        w = self._weights[index]
        if used + w <= self._capacity:
            taken = self._enumerate(index + 1, used + w, value + self._values[index])
            if taken > best:
                best = taken
        return best

    def count_combinations(self):
        """枚举每一件取或不取，逐个累加重量判超限，统计可行的装载组合个数。"""
        return self._count(0, 0)

    def _count(self, index, used):
        if index == len(self._weights):
            return 1
        total = self._count(index + 1, used)
        w = self._weights[index]
        if used + w <= self._capacity:
            total += self._count(index + 1, used + w)
        return total
