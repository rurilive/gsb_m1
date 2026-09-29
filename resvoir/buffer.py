"""resvoir 的朴素全量保留实现（改造前的现状）。

现在只有一种抽样器：KeepAll 把流入的每个元素连权重和标签一起原样记进
一个列表，留到最后的样本就是全部元素，内存随流入量线性增长。没有固定
容量，没有随机替换，没有加权选样，没有分层，没有可合并样本，均值与分位
都在全量数据上精确算。

固定内存的均匀蓄水池抽样、加权抽样、分层抽样、样本统计、样本合并与
内存有界性见任务描述。
"""


class KeepAll:
    """把流入元素全部留下来的朴素抽样器，样本等于全体。"""

    def __init__(self):
        self._entries = []
        self._seen = 0

    def add(self, item, weight=1, label=None):
        """留入一个元素，连权重与标签一起记下，返回这个元素。"""
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError("weight must be a number")
        if weight <= 0:
            raise ValueError("weight must be positive")
        self._entries.append((item, weight, label))
        self._seen += 1
        return item

    def seen(self):
        """返回累计流入的元素个数。"""
        return self._seen

    def items(self):
        """按流入顺序返回留住的全部元素。"""
        return tuple(item for item, _weight, _label in self._entries)

    def weights(self):
        """按流入顺序返回留住的全部权重。"""
        return tuple(weight for _item, weight, _label in self._entries)

    def sample(self):
        """返回样本，朴素实现里样本就是留住的全部元素。"""
        return self.items()

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(self.items())

    def total_weight(self):
        """返回留住的元素权重之和。"""
        return sum(weight for _item, weight, _label in self._entries)

    def mean(self):
        """返回留住的元素的加权均值，没有元素时返回 None。"""
        if not self._entries:
            return None
        total = self.total_weight()
        return sum(item * weight for item, weight, _label in self._entries) / total

    def quantile(self, q):
        """在留住的全部元素上精确取分位，q 在 0 到 1 之间。"""
        if isinstance(q, bool) or not isinstance(q, (int, float)):
            raise ValueError("q must be a number")
        if q < 0 or q > 1:
            raise ValueError("q must be in [0, 1]")
        if not self._entries:
            raise ValueError("empty sample has no quantile")
        values = sorted(item for item, _weight, _label in self._entries)
        if len(values) == 1:
            return values[0]
        pos = q * (len(values) - 1)
        low = int(pos)
        high = min(low + 1, len(values) - 1)
        frac = pos - low
        return values[low] * (1 - frac) + values[high] * frac

    def by_label(self):
        """按标签分组，返回标签到该组元素元组的映射。"""
        groups = {}
        for item, _weight, label in self._entries:
            groups.setdefault(label, []).append(item)
        return {label: tuple(items) for label, items in groups.items()}

    def clear(self):
        """清空留住的元素与累计流入计数。"""
        self._entries = []
        self._seen = 0

    def is_bounded(self):
        """朴素实现内存无界，恒为 False。"""
        return False
