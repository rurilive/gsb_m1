"""TwoPhaseSet：两阶段集合。

加入集与移除集各自只增，合并时分别取并集，所以合并结果与
顺序无关。元素一旦被移除就永远不在结果里。
"""


class TwoPhaseSet:
    """带移除的集合，元素类型需可排序。"""

    def __init__(self):
        # 元素一旦进来就不再出去，两个集合都只增不减
        self._added = set()
        self._removed = set()

    def add(self, item):
        """加入元素。"""
        self._added.add(item)
        return self

    def discard(self, item):
        """移除元素，元素进移除集，之后 add 同元素不再生效。"""
        self._removed.add(item)
        return self

    def contains(self, item):
        """元素当前是否在集合里。"""
        return item in self._added and item not in self._removed

    def value(self):
        """当前元素，按升序排列的元组。"""
        return tuple(sorted(self._added - self._removed))

    def merge(self, other):
        """就地并入另一个副本，加入集与移除集分别取并集。"""
        if not isinstance(other, TwoPhaseSet):
            raise TypeError("can only merge with TwoPhaseSet")
        self._added |= other._added
        self._removed |= other._removed
        return self

    def __repr__(self):
        return f"TwoPhaseSet({list(self.value())!r})"
