"""pathcover：朴素有向无环图最小路径覆盖工具（改造前基线）。

提供 PathCoverer 类，维护一张有向图（点是任意可哈希对象，边有向，
用有序对集合表示，重复边只算一次），支持加边、加孤立点、读图、求最
小路径覆盖的条数与方案、校验给定覆盖是否合法。当前实现一律靠枚举顶
点划分成路径的方案得到答案，规模稍大就跑不动。

拆点建二分图、求最大匹配那条路见任务描述。
"""

from .covering import (
    CoverError,
    Erro,
    GraphError,
    NodeError,
    PathCoverer,
)

__all__ = [
    "PathCoverer",
    "Erro",
    "GraphError",
    "NodeError",
    "CoverError",
]
