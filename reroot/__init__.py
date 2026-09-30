"""reroot: 树上换根聚合量的改造前基线工具。

以 Reroot 类载入一棵无向树，对每个结点单独当根重新深搜整棵树，
求出以该点为根时的子树大小、到其它所有点的距离之和以及树高。
做法直白、结果确定，但每个根都要把整棵树重走一遍，
结点一多就退化到平方量级。
"""

from .core import (
    DisconnectedError,
    Reroot,
    RerootError,
    RerootInputError,
    UnknownNodeError,
)

__all__ = [
    "Reroot",
    "RerootError",
    "RerootInputError",
    "UnknownNodeError",
    "DisconnectedError",
]
