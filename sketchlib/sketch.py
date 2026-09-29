"""精确频次统计（改造前基线）。

ExactCounter 用一个普通字典逐键记录真实计数，所有结果都精确，
代价是内存随不同键的数量线性增长。这里只保留现状行为，
概率计数素描（计数最小草图）是后续要做的改造目标。
"""


class SketchError(Exception):
    """本包所有业务异常的基类。"""


class ExactCounter(object):
    """用精确字典统计键出现次数的计数器。

    add(key) 把 key 的计数加一；count(key) 返回精确计数，键不存在返回 0；
    total() 返回全部键的计数之和；top(k) 返回计数最高的前 k 个键。

    计数一律精确，内存随不同键的数量线性增长。
    """

    def __init__(self):
        self._counts = {}

    def add(self, key, n=1):
        """把 key 的计数加上 n（n 缺省为 1），返回加上之后的新计数。"""
        if key is None:
            raise SketchError("键不能为空")
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise SketchError("增量必须是自然数")
        current = self._counts.get(key, 0)
        current += n
        self._counts[key] = current
        return current

    def count(self, key):
        """返回 key 的精确计数，键不存在返回 0。"""
        return self._counts.get(key, 0)

    def total(self):
        """返回全部键的计数之和。"""
        total = 0
        for value in self._counts.values():
            total += value
        return total

    def distinct(self):
        """返回已经出现过的不同键的数量。"""
        return len(self._counts)

    def top(self, k):
        """返回计数最高的前 k 个 (键, 计数)。

        排序口径写死：先按计数降序，计数相同时按插入序升序（先插入的靠前），
        因此对同一份键序列的结果是稳定的。k 为 0 或负数是没有结果的合法查询。
        """
        items = list(self._counts.items())
        # enumerate 保留插入序，作为平局时的第二排序键。
        ordered = sorted(
            enumerate(items),
            key=lambda pair: (-pair[1][1], pair[0]),
        )
        result = []
        for _, (key, value) in ordered:
            if len(result) >= k:
                break
            result.append((key, value))
        return result

    def __len__(self):
        return len(self._counts)

    def __contains__(self, key):
        return key in self._counts

    def __repr__(self):
        return "ExactCounter(distinct=%d, total=%d)" % (self.distinct(), self.total())
