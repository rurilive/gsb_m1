"""rankerx: 朴素的下一个更大元素查询工具。

当前只有朴素实现，见 rankerx/next.py：对每个位置都从它后面挨个往后找第一个
比它大的值，没有栈，没有一次遍历，也没有区间结构。单调栈系列改造见任务描述。
"""

from rankerx.next import BruteNext

__all__ = ["BruteNext"]
