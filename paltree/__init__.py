"""paltree: 朴素回文子串工具。

当前只有枚举子串当场判断的实现，见 paltree/tree.py。判断某子串是否回文
用双指针镜像比对，枚举全部回文子串把所有下标区间过一遍再挑，统计某位置
为结尾的回文个数、判断某个回文是否出现也都靠现算，代价随文本长度平方
增长。
回文树（回文自动机，失配链加长度零与长度负一两个根）、本质不同回文
统计、逐位置增量、各回文出现次数、最长最短回文与按长度分布见任务描述。
"""

from paltree.tree import (
    BrutePalTree,
    IllegalArgument,
    IndexOutOfRange,
    NotASubstring,
    PalTreeError,
)

__all__ = [
    "BrutePalTree",
    "PalTreeError",
    "IllegalArgument",
    "IndexOutOfRange",
    "NotASubstring",
]
