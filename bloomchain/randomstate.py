"""可复现的定种随机流。

RandomState 是 bloomchain 里取随机数的唯一入口：内部包一个 random.Random，
其余模块只许经它拿随机数，不得直接碰 random 模块，否则同一 seed 跨进程
跑不出一致的盐与层展开。
"""

import random


class RandomState:
    """定种随机流。"""

    __slots__ = ("seed", "_rng")

    def __init__(self, seed):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)

    def getrandbits(self, n):
        """取 n 位无符号整数。"""
        if n < 1:
            raise ValueError("n must be >= 1")
        return self._rng.getrandbits(n)

    def below(self, bound):
        """取 [0, bound) 内的整数。"""
        bound = int(bound)
        if bound < 1:
            raise ValueError("bound must be >= 1")
        return self._rng.randrange(bound)

    def salt(self):
        """取一个非零的 64 位盐，用来区分不同层的哈希展开。"""
        return self.getrandbits(64) | 1

    def fork(self, label):
        """派生子流：同 seed 同 label 派生的流互相独立又可复现。"""
        return RandomState((self.seed * 0x100000001B3 + int(label)) & ((1 << 63) - 1))
