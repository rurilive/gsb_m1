"""G-Counter：只增计数器。

每个槽位各自累加，合并时同槽位取较大值。合并满足交换律、
结合律、幂等，副本之间合并多少次、按什么顺序合并，结果一致。
"""


class GCounter:
    """多槽位只增计数器。

    replica_id: 本副本标识，非空字符串。
    """

    def __init__(self, replica_id):
        if not isinstance(replica_id, str) or not replica_id:
            raise ValueError("replica_id must be a non-empty string")
        self.replica_id = replica_id
        # 槽位名 -> 计数
        self._counts = {}

    def incr(self, key, n=1):
        """给槽位 key 加 n，n 必须为正整数。"""
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise ValueError("n must be a positive integer")
        self._counts[key] = self._counts.get(key, 0) + n
        return self

    def value(self):
        """所有槽位计数之和。"""
        return sum(self._counts.values())

    def merge(self, other):
        """就地并入另一个副本，同槽位取较大值。"""
        if not isinstance(other, GCounter):
            raise TypeError("can only merge with GCounter")
        for key, count in other._counts.items():
            if count > self._counts.get(key, 0):
                self._counts[key] = count
        return self

    def __repr__(self):
        return f"GCounter({self.replica_id!r}, value={self.value()})"
