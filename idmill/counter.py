"""idmill 的最朴素实现：一个进程内自增计数器。

现状只有单一的整型自增：每次调用返回当前值再把计数器加一，从 0 开始。
没有时间位、没有工作节点位、没有时钟回拨处理，也没有任何解析能力。
"""


class Counter(object):
    """进程内自增计数器，从 0 开始，每次加一。"""

    def __init__(self, start=0):
        self._value = start

    @property
    def value(self):
        """下一个将要发出的值。"""
        return self._value

    def next_id(self):
        """返回当前值，并把计数器加一。"""
        current = self._value
        self._value = current + 1
        return current
