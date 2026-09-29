"""treepath: 内存里的朴素有根树路径工具。

当前只有逐节点遍历的实现，见 treepath/tree.py。深度逐层上爬、最近公共
祖先逐层上爬、路径和与子树和逐个节点累加、路径更新逐个节点改写。
重链剖分、跳链的路径与子树统计见任务描述。
"""

from treepath.tree import NodeNotFound, TreeError, WalkTree

__all__ = ["WalkTree", "TreeError", "NodeNotFound"]
