"""改造前的朴素集合：add、contains、remove 都在一个 dict 上兜着。

这是布谷鸟过滤器落地前的基线实现。没有桶、没有指纹、没有踢出，也不
扩容，命中判定精确、不产生假阳性，语义上是正确但朴素的一版。
"""


class NaiveSet:
    """用 dict 做成员判定的朴素集合。

    add 登记一个键，contains 判定键在不在，remove 删一个键。
    同一个键重复 add 只算一份成员；capacity 只是构造时记下的名义容量，
    这里不做限制，塞得下放得下。
    """

    def __init__(self, capacity=1024):
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._members = {}

    def add(self, key):
        """登记一个键。键已存在则返回 False，是新键返回 True。"""
        if key in self._members:
            return False
        self._members[key] = True
        return True

    def __contains__(self, key):
        return key in self._members

    def remove(self, key):
        """删一个键。删到返回 True，键本来就不在返回 False。"""
        if key in self._members:
            del self._members[key]
            return True
        return False

    def contains(self, key):
        """contains 的方法形式，等同 in。"""
        return key in self._members

    def __len__(self):
        return len(self._members)

    def stats(self):
        """计数快照，独立 dict。"""
        return {
            "size": len(self._members),
            "capacity": self.capacity,
        }
