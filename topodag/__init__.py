"""topodag：有向无环图拓扑排序的朴素实现。

现状用相邻结点表存有向边，求拓扑序靠反复全表线性扫描找零入度点并逐个摘除，
每一轮重扫全部结点与出去的边，有环时某轮找不到零入度点即判环。口径直白、结果
确定，但代价随点数与边数平方级上涨。异常统一从 Erro 派生。
"""

from topodag.graph import (
    DirectedGraph,
    Erro,
    InvalidGraphError,
    NodeNotFoundError,
)

__all__ = [
    "DirectedGraph",
    "Erro",
    "InvalidGraphError",
    "NodeNotFoundError",
]
