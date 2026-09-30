"""dagtopo: 有向图上朴素但正确的拓扑序、依赖调度与可达性计数。

当前只有反复在整张图里线性扫描找零入度点的实现，见 dagtopo/graph.py。
用入度队列一次求出拓扑序且可选点取编号最小、在拓扑序上求最早开始时间与
关键路径、对有环图给出一个具体环、每点的可达与反向可达计数，见任务描述。
"""

from dagtopo.graph import (
    DirectedGraph,
    TopoError,
    InvalidGraphError,
    NodeNotFoundError,
)

__all__ = [
    "DirectedGraph",
    "TopoError",
    "InvalidGraphError",
    "NodeNotFoundError",
]
