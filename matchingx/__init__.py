"""matchingx：朴素二分匹配工具（改造前基线）。

提供 BrutePair 类，维护一张二分图（左侧一组点、右侧一组点，
边用对集合表示），支持加边、判断是否存在覆盖全部左侧点的完美匹配、
求最大匹配条数，以及在某个已求出的匹配里查询左侧点配到的右侧点。
当前实现一律靠回溯枚举全部匹配来得到答案，最坏情形是指数级的。
"""

from .pair import BrutePair, MatchingError, NotMatchedError, UnknownPointError

__all__ = ["BrutePair", "MatchingError", "NotMatchedError", "UnknownPointError"]
