"""lctx: 内存里的朴素动态森林工具。

当前只有邻接集合加当场遍历的实现，见 lctx/dtree.py。连通性用一次深度优先
判断，路径和与路径最值沿路径逐节点累加或比较，子树和把子树逐节点走一遍，
连通分量个数每次都从头数一遍，换根则把整棵树的根标记整体重扫一遍。

以动态树（优先路径与实链剖分）为核心的对数级工具集见任务描述。
"""

from lctx.dtree import Dtree, DtreeError, NoSuchEdge, NoSuchNode

__all__ = ["Dtree", "DtreeError", "NoSuchNode", "NoSuchEdge"]
