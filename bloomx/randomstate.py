"""可复现的定种随机流。

RandomState 是 bloomx 里取随机数的唯一入口：内部包一个 random.Random，
其余模块只许经它拿随机数，不得直接碰 random 模块，否则同一 seed 跨进程
跑不出一样的位模式。
"""

import random


class RandomState:
    """定种随机流。

    构造参数 seed 决定整个流。getrandbits 取 n 位无符号整数，below 取
    [0, bound) 内的整数，choices 取不重复下标组合。同一个 seed 造出来的
    两个实例，调用序列一致则输出一致，与 Python 版本无关的稳定性由
    random.Random 的算法保证。
    """

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

    def shuffle(self, items):
        """就地打乱一个列表，返回它本身。"""
        self._rng.shuffle(items)
        return items

    def fork(self, label):
        """派生子流：同 seed 同 label 派生的流互相独立又可复现。"""
        return RandomState((self.seed * 0x100000001B3 + int(label)) & ((1 << 63) - 1))
