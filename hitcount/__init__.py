"""hitcount: 一个朴素的全量重频计数小库，纯标准库，无外部依赖。

现阶段只有一层：NaiveCounter 给每个不同的元素记一个精确计数，计数
存在字典里，元素种类一多内存就无界。没有有界结构、没有重频查询、
没有误差上界、没有可合并语义，也没有时间窗口与驱逐记账。
"""

from .naive import NaiveCounter

__all__ = ["NaiveCounter"]