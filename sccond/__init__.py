"""sccond: 有向图连通性工具的朴素基线（改造前）。

对外只暴露 Digraph、错误基类，以及逐对可达搜索的规模估算。
"""

from .scc import (
    Digraph,
    GraphError,
    UnknownVertexError,
    naive_pair_count,
)

__all__ = [
    "Digraph",
    "GraphError",
    "UnknownVertexError",
    "naive_pair_count",
]
