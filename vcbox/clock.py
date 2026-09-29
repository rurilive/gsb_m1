"""最朴素的逻辑时钟：一个自增的整数计数。

只维护一个进程内的单调整数，用数值大小比较先后，不含向量、偏序、合并
或并发判定的任何概念。
"""


class Clock:
    """整数逻辑时钟，tick 一次计数加一。"""

    def __init__(self, value=0):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("初始值必须是整数")
        if value < 0:
            raise ValueError("初始值不能为负")
        self._value = value

    def tick(self):
        """推进一个本地事件，返回推进后的计数。"""
        self._value += 1
        return self._value

    @property
    def value(self):
        return self._value

    def __eq__(self, other):
        if not isinstance(other, Clock):
            return NotImplemented
        return self._value == other._value

    def __lt__(self, other):
        if not isinstance(other, Clock):
            return NotImplemented
        return self._value < other._value

    def __le__(self, other):
        if not isinstance(other, Clock):
            return NotImplemented
        return self._value <= other._value

    def __repr__(self):
        return "Clock(%d)" % self._value
