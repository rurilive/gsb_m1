"""lcatree: 有根树上朴素但正确的最近公共祖先与路径查询。

当前只有沿父指针逐级上溯的实现，见 lcatree/tree.py。
倍增祖先表、树上两点距离、路径判定、路径排序、路径相交，见任务描述。
"""

from lcatree.tree import Tree, TreeError

__all__ = ["Tree", "TreeError"]
