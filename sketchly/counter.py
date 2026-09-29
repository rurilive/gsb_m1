"""sketchly 的现有实现。

这里只有一套最朴素的精确计数：每见到一个键就把它在字典里的计数加
一，value 返回该键当前的精确次数。计数是精确的，但字典会随键的种类
一直涨，键空间一大内存就无界；也拿不出固定内存的估算与误差界，没法
把两份计数并起来，没有计数器数组、没有哈希定位，更没有单侧误差、
误差界与区间查询这些概念。
"""


class ExactCounter:
    """朴素的全量精确计数字典。

    只做一件确定的事：把每个见过的键映射到一个精确次数。所有键一视
    同仁地被留在同一个字典里，谁也不丢，所以键种类越多占的内存越多。
    """

    def __init__(self):
        self._counts = {}

    def add(self, key, amount=1):
        """把一个键的计数加 amount。

        key 必须是非空字符串，否则抛 ValueError。amount 必须是不小于
        零的整数，否则抛 ValueError。重复加入把计数累加。
        """
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty str")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("amount must be a non-negative int")
        self._counts[key] = self._counts.get(key, 0) + amount

    def add_many(self, keys):
        """批量加入一串键，每个键各加一次。"""
        for key in keys:
            self.add(key)

    def value(self, key):
        """返回某个键的精确计数，从没记过则为零。"""
        return self._counts.get(key, 0)

    def total(self):
        """全部键的计数之和。"""
        return sum(self._counts.values())

    def keys(self):
        """当前记过的全部键。"""
        return list(self._counts.keys())

    def merge(self, other):
        """把另一个计数字典的计数逐键加进来，返回 self。

        只接受 ExactCounter，否则抛 ValueError。合并是精确的。
        """
        if not isinstance(other, ExactCounter):
            raise ValueError("other must be an ExactCounter")
        for key, count in other._counts.items():
            self._counts[key] = self._counts.get(key, 0) + count
        return self

    def reset(self):
        """清空全部键，回到刚建立时的状态。"""
        self._counts = {}
