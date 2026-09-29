"""segtre: 朴素逐元素区间求和。

当前只有一个朴素实现，见 segtre/array.py：区间查询就是把区间里的每个
元素挨个累加一遍。线段树建树、区间最值、点更新、区间加与区间赋值的懒惰
传播、可配置合并函数、前缀二分与随机序列对拍见任务描述。
"""

from segtre.array import SegArray

__all__ = ["SegArray"]
