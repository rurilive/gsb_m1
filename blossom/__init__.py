"""blossom：朴素一般图匹配工具（改造前基线）。

提供 GraphMatcher 类，维护一张一般图（点是任意可哈希对象，边无向，
用对集合表示，重复边只算一次），支持加边、读图、求最大匹配条数与
方案、判定完美匹配、判断给定匹配是否最大。当前实现一律靠回溯枚举
全部边组合得到答案，规模稍大就跑不动。

带花树的增广路求匹配、奇环缩点那条路见任务描述。
"""

from .matching import (
    Erro,
    GraphError,
    GraphMatcher,
    MatchError,
    NodeError,
    NotMatchedError,
)

__all__ = [
    "GraphMatcher",
    "Erro",
    "GraphError",
    "NodeError",
    "MatchError",
    "NotMatchedError",
]
