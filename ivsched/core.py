"""ivsched：区间调度与区间集合统计的朴素实现。

现状只有一条最直白的路：核心类持有一批闭区间，求最大不相交区间数与带权最大权值
不相交集时，把区间下标的全集枚举成一个个子集，再对每个子集逐对判断是否重叠，
留下两两不重叠的子集里最大最重的那一批。口径直白、结果确定，但子集个数随区间数
指数级上涨。异常统一从 Erro 派生。
"""


class Erro(Exception):
    """本模块对外抛出异常的公共基类。"""


class BadInterval(Erro):
    """区间端点非法：非整数，或起点大于终点。"""


class BadWeight(Erro):
    """区间权值非法：不是整数（含布尔）或为负。"""


class UnknownInterval(Erro):
    """访问了未登记过的区间下标。"""


def _is_int(value):
    """严格整数判定，布尔不算整数。"""
    return isinstance(value, int) and not isinstance(value, bool)


class NaiveIntervalScheduler:
    """闭区间的朴素调度器，全部结论靠穷举全部子集得到。"""

    def __init__(self):
        self._starts = []
        self._ends = []
        self._weights = []
        self._subsets = 0
        self._overlap_checks = 0
        self._weight_sums = 0

    # ---- 登记与读取 -------------------------------------------------------

    def add(self, start, end, weight=1):
        """登记一个闭区间，返回它的下标。

        端点须为整数且起点不大于终点，权值须为非负整数。
        """
        if not _is_int(start) or not _is_int(end):
            raise BadInterval("区间端点必须是整数")
        if start > end:
            raise BadInterval("区间起点不得大于终点")
        if not _is_int(weight):
            raise BadWeight("区间权值必须是整数")
        if weight < 0:
            raise BadWeight("区间权值不得为负")
        self._starts.append(start)
        self._ends.append(end)
        self._weights.append(weight)
        return len(self._starts) - 1

    def size(self):
        """已登记的区间个数。"""
        return len(self._starts)

    def intervals(self):
        """全部区间，形如（下标，起点，终点，权值）的列表。"""
        return [
            (i, self._starts[i], self._ends[i], self._weights[i])
            for i in range(self.size())
        ]

    def interval(self, index):
        """取一个区间，形如（起点，终点，权值）。"""
        if not _is_int(index) or index < 0 or index >= self.size():
            raise UnknownInterval("未登记的区间下标")
        return (self._starts[index], self._ends[index], self._weights[index])

    # ---- 重叠判定 ---------------------------------------------------------

    def overlaps(self, a, b):
        """两个闭区间是否有公共点，端点相等算重叠。"""
        return self._starts[a] <= self._ends[b] and self._starts[b] <= self._ends[a]

    # ---- 穷举 -------------------------------------------------------------

    def _disjoint_selections(self):
        """枚举全部两两不重叠的子集，返回按升序排好的下标元组列表。

        逐个子集逐对判定是否重叠，边枚举边累计规模计数。
        """
        n = self.size()
        found = []
        for mask in range(1 << n):
            self._subsets += 1
            chosen = [i for i in range(n) if (mask >> i) & 1]
            ok = True
            for a in range(len(chosen)):
                for b in range(a + 1, len(chosen)):
                    self._overlap_checks += 1
                    if self.overlaps(chosen[a], chosen[b]):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                found.append(tuple(chosen))
        return found

    def _weight_of(self, selection):
        """一个选择的总权值，顺带累计求和次数。"""
        total = 0
        for i in selection:
            total += self._weights[i]
        self._weight_sums += 1
        return total

    # ---- 对外结论 ---------------------------------------------------------

    def all_disjoint_selections(self):
        """全部两两不重叠的子集，按升序下标元组给出（含空集）。"""
        return self._disjoint_selections()

    def max_disjoint_count(self):
        """最大不相交区间数，没有任何区间时为零。"""
        best = 0
        for sel in self._disjoint_selections():
            if len(sel) > best:
                best = len(sel)
        return best

    def max_weighted_value(self):
        """带权最大权值不相交集的总权值，没有任何区间时为零。"""
        best = 0
        for sel in self._disjoint_selections():
            value = self._weight_of(sel)
            if value > best:
                best = value
        return best

    def best_disjoint_selection(self):
        """最大不相交的一批区间下标。

        在所有区间个数最多的不重叠子集里，取下标元组按字典序最小者；同长度元组
        直接逐个比较下标，小者在前。
        """
        best = None
        for sel in self._disjoint_selections():
            if best is None or len(sel) > len(best):
                best = sel
            elif len(sel) == len(best) and sel < best:
                best = sel
        if best is None:
            return ()
        return best

    def best_weighted_selection(self):
        """带权最大权值的一批区间下标。

        先看总权值最大，权值相同时再看下标元组按字典序最小；元组长度不同时，
        按元组自身的字典序比较，短者是长者的前缀时更小。
        """
        best = None
        best_value = None
        for sel in self._disjoint_selections():
            value = self._weight_of(sel)
            if best is None or value > best_value:
                best, best_value = sel, value
            elif value == best_value and sel < best:
                best = sel
        if best is None:
            return ()
        return best

    # ---- 规模计数 ---------------------------------------------------------

    def count_subsets(self):
        """累计已枚举过的子集个数。"""
        return self._subsets

    def count_overlap_checks(self):
        """累计已做过的区间两两重叠判定次数。"""
        return self._overlap_checks

    def count_weight_sums(self):
        """累计已做过的不重叠子集求和次数。"""
        return self._weight_sums

    def cost_report(self):
        """规模计数一表，键为 subsets、overlap_checks、weight_sums。"""
        return {
            "subsets": self._subsets,
            "overlap_checks": self._overlap_checks,
            "weight_sums": self._weight_sums,
        }
