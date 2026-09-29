"""对象借还池：借出与归还对象，池内空闲优先复用。

当前是最朴素的实现：借的时候池是空的就现造一个，还的时候把对象
随手塞回一个列表。没有容量上限，没有空闲回收，没有尺寸分档，也
没有借出标记与生命周期管理。
"""


class Block:
    """池里的一个对象：带序号与可选负载。"""

    __slots__ = ("bid", "payload")

    def __init__(self, bid, payload=None):
        self.bid = bid
        self.payload = payload

    def __repr__(self):
        return f"<Block #{self.bid}>"


class BorrowPool:
    """一进一出的对象借还池。

    factory: 可选，建造新对象的可调用对象；缺省由池自己造 Block。
    """

    def __init__(self, factory=None):
        self._factory = factory
        self._idle = []
        self._created = 0

    @property
    def idle(self):
        """当前空闲对象数量。"""
        return len(self._idle)

    @property
    def created(self):
        """累计新建对象数量。"""
        return self._created

    def borrow(self):
        """借出一个对象：池里有空闲就复用，否则新建。"""
        if self._idle:
            return self._idle.pop()
        self._created += 1
        if self._factory is None:
            return Block(self._created)
        return self._factory()

    def give_back(self, block):
        """把对象塞回空闲列表。"""
        self._idle.append(block)
