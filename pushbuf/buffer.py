"""最朴素的无界先进先出缓冲，纯标准库。

现有能力（基线）：

- UnboundedBuffer() 建一个内存缓冲，内部就是一个列表；
- put(item) 永远成功，把元素追加到队尾并返回元素本身；
- get() 从队首取出一个元素并返回，缓冲为空返回 (False, None)；
- peek() 看一眼队首元素但不取出，缓冲为空返回 (False, None)；
- empty() / __len__ 报缓冲是否为空与当前元素个数；
- clear() 清空缓冲。

这层没有容量上限，put 永远不会失败，所以写者不必等待也无需退让；没有
水位，也没有背压信号；被拒绝与被丢弃都无从谈起，更谈不上唤醒顺序与计量。
带背压的有界队列要在它之上另建实现。
"""


class UnboundedBuffer:
    """无界先进先出缓冲，put 永远成功。"""

    def __init__(self):
        self._items = []

    def put(self, item):
        """把元素追加到队尾并返回元素本身，永远成功。"""
        self._items.append(item)
        return item

    def get(self):
        """从队首取出一个元素。命中返回 (True, item)，空缓冲返回 (False, None)。"""
        if not self._items:
            return (False, None)
        return (True, self._items.pop(0))

    def peek(self):
        """看一眼队首元素但不取出。命中返回 (True, item)，空缓冲返回 (False, None)。"""
        if not self._items:
            return (False, None)
        return (True, self._items[0])

    def empty(self):
        """缓冲是否为空。"""
        return not self._items

    def clear(self):
        """清空缓冲。"""
        self._items = []

    def __len__(self):
        return len(self._items)
