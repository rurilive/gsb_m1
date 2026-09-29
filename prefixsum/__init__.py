"""prefixsum: 朴素逐项累加的区间和工具。

当前只有朴素实现，见 prefixsum/sum.py：区间查询就是从区间起点开始把
每个元素挨个累加一遍，点更新就是就地改一个位置。没有树状数组，没有差分，
没有二维结构。树状数组改造见任务描述。
"""

from prefixsum.sum import ScanSum

__all__ = ["ScanSum"]
