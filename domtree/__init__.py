"""domtree: 朴素支配关系工具。

当前只有逐点删点判可达的实现，见 domtree/dominator.py。求一个起点的全部
支配点时，对起点可达的每个候选点都单独把该点拿掉、单独从起点搜一遍，代价
按点数乘边数甚至更高增长，规模一大就顶不住。

按深度优先搜索编号、半支配点与并查集求交求直接支配点与支配树，以及逐点删
点这条独立对照路径、边界与确定性见任务描述。
"""

from domtree.dominator import (
    DirectedGraph,
    Erro,
    IllegalArgument,
    UnknownNode,
)

__all__ = [
    "DirectedGraph",
    "Erro",
    "IllegalArgument",
    "UnknownNode",
]
