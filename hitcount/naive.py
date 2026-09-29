"""hitcount 的现有实现。

这里只有一套朴素的全量计数：每见到一个元素就把它的计数加一，计数
存在一个字典里，每个不同的元素占一个键。计数是精确的，但字典会随
不同元素的个数一直涨，元素基数大时内存无界；也拿不出重频查询、误差
上界、可合并的语义和时间窗口，更没有驱逐与记账。
"""


class NaiveCounter:
    """朴素的全量精确计数器。

    只做一件确定的事：给每个不同的元素维护一个精确的整数计数。所有
    元素一视同仁地被记住，谁也不淘汰，所以元素种类越多占的内存越多。
    """

    def __init__(self):
        self._counts = {}
        self._total = 0

    def add(self, key, count=1):
        """给元素 key 记 count 次，缺省一次。

        count 必须是正整数，否则抛 ValueError；key 必须可哈希且非空
        字符串，否则抛 ValueError。
        """
        if not isinstance(key, str) or not key:
            raise ValueError("key must be a non-empty str")
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("count must be a positive int")
        if count <= 0:
            raise ValueError("count must be a positive int")
        self._counts[key] = self._counts.get(key, 0) + count
        self._total += count

    def estimate(self, key):
        """元素 key 的精确计数；没见过返回零。"""
        return self._counts.get(key, 0)

    def count(self, key):
        """元素 key 的精确计数，等价于 estimate。"""
        return self._counts.get(key, 0)

    def total(self):
        """累计记入的总次数。"""
        return self._total

    def distinct(self):
        """当前记住的不同元素个数。"""
        return len(self._counts)

    def top_k(self, k):
        """出现次数最多的前 k 个元素，按次数降序。

        k 必须是非负整数，否则抛 ValueError。同次数时按元素字典序
        升序排列，保证结果确定。返回 (元素, 精确次数) 的列表。
        """
        if isinstance(k, bool) or not isinstance(k, int):
            raise ValueError("k must be a non-negative int")
        if k < 0:
            raise ValueError("k must be a non-negative int")
        ranked = sorted(self._counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:k]

    def reset(self):
        """清空全部计数，回到刚建立时的状态。"""
        self._counts = {}
        self._total = 0