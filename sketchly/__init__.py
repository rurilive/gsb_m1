"""sketchly: 一个频次计数小库，纯标准库，无外部依赖。

现阶段只有一层：ExactCounter 给每个键留一个精确计数，value 返回某个
键当前的精确次数。键的种类一多，占据的内存就跟着键空间一起涨，既
没有固定大小的计数器数组，也没有估算与误差界，不能把两份计数并到
一起，更没有单侧误差与区间查询的概念。
"""

from .counter import ExactCounter

__all__ = ["ExactCounter"]
