"""sccdag: 朴素有向图可达工具（改造前基线）。

提供 ReachGraph 类与异常体系，图以邻接表保存，支持加节点、加边、
查询邻居与出度，以及单点可达和两两互达判断。当前不提供任何分量级
信息，互达相关问题只能成对询问，每次都要正反跑两遍深度优先遍历。
"""

from .graph import (
    GraphError,
    ReachGraph,
    SccError,
    UnknownNodeError,
)

__all__ = [
    "ReachGraph",
    "SccError",
    "UnknownNodeError",
    "GraphError",
]
