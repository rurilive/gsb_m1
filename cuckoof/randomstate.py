"""可复现的定种随机流。

RandomState 是 cuckoof 里取随机数的唯一入口：内部包一个 random.Random，
其余模块只许经它拿随机数，不得直接碰 random 模块，否则同一 seed 跨进程
跑不出一致的踢出路径。
"""

import random


class RandomState:
    """定种随机流。"""

    __slots__ = ("seed", "_rng")

    def __init__(self, seed):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)

    def below(self, bound):
        """取 [0, bound) 内的整数。"""
        bound = int(bound)
        if bound < 1:
            raise ValueError("bound must be >= 1")
        return self._rng.randrange(bound)

    def shuffle(self, items):
        """就地打乱一个列表，返回它本身。"""
        self._rng.shuffle(items)
        return items

    def fork(self, label):
        """派生子流：同 seed 同 label 派生的流互相独立又可复现。"""
        return RandomState((self.seed * 0x100000001B3 + int(label)) & ((1 << 63) - 1))
