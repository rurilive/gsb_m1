"""lctlib: 内存里的朴素动态森林工具。

当前只有邻接集合加遍历的实现，见 lctlib/forest.py。连通性用一次深度
优先判断，路径和沿路径逐节点累加，子树和把子树逐节点走一遍，连通分量
个数每次都从头数一遍。
动态树（连边断边维持路径信息）、子树统计、对数级连通与分量计数见任务
描述。
"""

from lctlib.forest import FlatForest, LctError, NoSuchEdge, NoSuchNode

__all__ = ["FlatForest", "LctError", "NoSuchNode", "NoSuchEdge"]
