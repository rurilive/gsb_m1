"""intervalx 基线实现：区间集合工具的最朴素做法。

全部能力都用两两比较或逐点逐区间判定完成，规模一大就慢，但结果正确。
本文件是改造前的现状，不是最终应当的样子。
"""

__all__ = [
    "IntervalSet",
    "Erro",
    "IntervalErro",
    "TargetErro",
    "IndexErro",
]

# 求两区间并集时的失败哨兵。
NONE = None


class Erro(Exception):
    """本包全部异常的基类。"""


class IntervalErro(Erro):
    """区间数据不合法。"""


class TargetErro(Erro):
    """目标区间不合法。"""


class IndexErro(Erro):
    """下标不合法。"""


def _is_int(x):
    """严格整数判定，布尔不算整数。"""
    return isinstance(x, int) and not isinstance(x, bool)


def _check_pair(pair, what, erro=IntervalErro):
    if not isinstance(pair, (tuple, list)) or len(pair) != 2:
        raise erro("%s 必须是二元组" % what)
    lo, hi = pair[0], pair[1]
    if not _is_int(lo) or not _is_int(hi):
        raise erro("%s 端点必须是整数" % what)
    if lo > hi:
        raise erro("%s 左端不得大于右端" % what)
    return (lo, hi)


class IntervalSet(object):
    """一个区间集合，附带覆盖与合并等朴素查询。"""

    def __init__(self, intervals=()):
        items = []
        if not isinstance(intervals, (tuple, list)):
            raise IntervalErro("区间集合必须是元组或列表")
        for i, raw in enumerate(intervals):
            items.append(_check_pair(raw, "第 %d 个区间" % i))
        self._items = items

    @property
    def intervals(self):
        return list(self._items)

    def count(self):
        return len(self._items)

    # ---------- 逐点逐区间判定 ----------

    def covers_point(self, point):
        if not _is_int(point):
            raise IntervalErro("查询点必须是整数")
        n = len(self._items)
        hits = []
        for i in range(n):
            lo, hi = self._items[i]
            if lo <= point and point <= hi:
                hits.append(i)
        return hits

    def coverage_count(self, point):
        return len(self.covers_point(point))

    def is_covered(self, point):
        n = len(self._items)
        for i in range(n):
            lo, hi = self._items[i]
            if lo <= point and point <= hi:
                return True
        return False

    def coverage_length(self):
        # 先取全部端点，再对每一段逐个中点逐区间判定。
        if not self._items:
            return 0
        points = []
        for lo, hi in self._items:
            points.append(lo)
            points.append(hi)
        points = _unique_sorted(points)
        total = 0
        for k in range(len(points) - 1):
            a = points[k]
            b = points[k + 1]
            mid = (a + b) // 2
            if a < b and self.is_covered(mid):
                total += b - a
        return total

    def max_overlap(self):
        # 遍历全部整点，对每个点逐个数覆盖它的区间。
        if not self._items:
            return 0
        points = []
        lo_first = self._items[0][0]
        hi_first = self._items[0][1]
        for lo, hi in self._items:
            points.append(lo)
            points.append(hi)
            if lo < lo_first:
                lo_first = lo
            if hi > hi_first:
                hi_first = hi
        best = 0
        p = lo_first
        while p <= hi_first:
            c = 0
            for lo, hi in self._items:
                if lo <= p and p <= hi:
                    c += 1
            if c > best:
                best = c
            p += 1
        return best

    # ---------- 两两比较 ----------

    def merge(self):
        # 反复把每一对可连通的区间合成一段，直到不再变化。
        current = [(lo, hi) for lo, hi in self._items]
        changed = True
        while changed:
            changed = False
            n = len(current)
            for i in range(n):
                if changed:
                    break
                for j in range(n):
                    if i == j:
                        continue
                    merged = _try_join(current[i], current[j])
                    if merged is not None:
                        rest = [
                            current[k]
                            for k in range(n)
                            if k != i and k != j
                        ]
                        current = rest + [merged]
                        changed = True
                        break
        current.sort()
        return current

    def intersection(self):
        # 逐对区间求交，再把结果合并去重；等价于被两个及以上区间覆盖的区域。
        if not self._items:
            return []
        n = len(self._items)
        result = []
        for i in range(n):
            for j in range(i + 1, n):
                a = self._items[i]
                b = self._items[j]
                lo = a[0]
                if b[0] > lo:
                    lo = b[0]
                hi = a[1]
                if b[1] < hi:
                    hi = b[1]
                if lo <= hi:
                    result.append((lo, hi))
        return IntervalSet(result).merge()

    def union_length(self):
        return self.coverage_length()

    def contains_pair(self, i, j):
        # 求区间下标 i 与 j 的包含关系，四次端点比较。
        n = len(self._items)
        if not _is_int(i) or not _is_int(j):
            raise IndexErro("下标必须是整数")
        if i < 0 or i >= n or j < 0 or j >= n:
            raise IndexErro("下标越界")
        a = self._items[i]
        b = self._items[j]
        a_in_b = a[0] >= b[0] and a[1] <= b[1]
        b_in_a = b[0] >= a[0] and b[1] <= a[1]
        return (a_in_b, b_in_a)

    def containment(self):
        # 对当前全部区间两两求包含关系，返回被包含对。
        if not self._items:
            return []
        result = []
        for i in range(len(self._items)):
            for j in range(len(self._items)):
                if i == j:
                    continue
                if self.contains_pair(i, j)[0]:
                    result.append((i, j))
        return result

    # ---------- 贪心最少覆盖 ----------

    def cover_with(self, target):
        """用最少区间覆盖目标区间，返回下标序列；不可覆盖时返回空列表。

        先从当前右端逐段往前推，搜出覆盖剩余段所需的最少区间数；
        再从目标左端出发，每步在能延伸右端的候选里取下标最小、且选它之后
        仍能达到最少总数的那个，从而在并列方案里取下标序列字典序最小者。
        """
        tgt = _check_pair(target, "目标区间", TargetErro)
        t_lo, t_hi = tgt
        n = len(self._items)

        if t_lo == t_hi:
            idx = self._first_covering(t_lo)
            return [] if idx is None else [idx]

        right = t_lo
        used = []
        while right < t_hi:
            rest = self._min_needed(right, t_hi)
            if rest is None:
                return []
            chosen = None
            for i in range(n):
                lo, hi = self._items[i]
                if lo <= right and hi > right:
                    sub = self._min_needed(hi, t_hi)
                    if sub is not None and sub + 1 == rest:
                        chosen = i
                        break
            if chosen is None:
                return []
            used.append(chosen)
            right = self._items[chosen][1]
        return used

    def _min_needed(self, right, t_hi):
        """从 right 到 t_hi 还需的最少区间数，无法推进时返回空。"""
        if right >= t_hi:
            return 0
        count = 0
        r = right
        while r < t_hi:
            best_hi = r
            for lo, hi in self._items:
                if lo <= r and hi > best_hi:
                    best_hi = hi
            if best_hi == r:
                return NONE
            count += 1
            r = best_hi
        return count

    def _first_covering(self, point):
        for i in range(len(self._items)):
            lo, hi = self._items[i]
            if lo <= point and point <= hi:
                return i
        return None

    # ---------- 全套结果与朴素代价 ----------

    def solve_all(self, target):
        merged = self.merge()
        inter = self.intersection()
        length = self.union_length()
        pick = self.cover_with(target)
        return {
            "merged": merged,
            "intersection": inter,
            "union_length": length,
            "cover": pick,
        }

    def comparison_count(self):
        """朴素两两比较次数，用于与更聪明的做法对照规模。"""
        n = len(self._items)
        pair = n * (n - 1)
        return pair + n * n

    def access_count(self):
        """朴素逐点逐区间访问次数，扫描线路径基线恒为零。"""
        n = len(self._items)
        if n == 0:
            return 0
        lo_first = self._items[0][0]
        hi_first = self._items[0][1]
        for lo, hi in self._items:
            if lo < lo_first:
                lo_first = lo
            if hi > hi_first:
                hi_first = hi
        return (hi_first - lo_first + 1) * n

    # ---------- 独立慢速做法 ----------

    def independent_brute_merge(self):
        """独立做法一：把逐点与逐段单独判定出的覆盖片拼起来再合并。

        先对每个端点单独判定是否被覆盖，得到退化为一点的片；再对每对相邻
        端点取中点判定是否被覆盖，得到一小段片；全部片排序后顺序合并。
        """
        if not self._items:
            return []
        points = []
        for lo, hi in self._items:
            points.append(lo)
            points.append(hi)
        points = _unique_sorted(points)
        pieces = []
        for p in points:
            if self.is_covered(p):
                pieces.append((p, p))
        for k in range(len(points) - 1):
            a = points[k]
            b = points[k + 1]
            mid = (a + b) // 2
            if a < b and self.is_covered(mid):
                pieces.append((a, b))
        pieces.sort()
        merged = []
        for piece in pieces:
            if merged and merged[-1][1] >= piece[0]:
                last = merged[-1]
                hi = last[1]
                if piece[1] > hi:
                    hi = piece[1]
                merged[-1] = (last[0], hi)
            else:
                merged.append(piece)
        return merged

    def independent_brute_max_overlap(self):
        """独立做法二：只在全部端点上逐点逐区间判定，取最大覆盖数。"""
        if not self._items:
            return 0
        points = []
        for lo, hi in self._items:
            points.append(lo)
            points.append(hi)
        best = 0
        for p in _unique_sorted(points):
            c = 0
            for lo, hi in self._items:
                if lo <= p and p <= hi:
                    c += 1
            if c > best:
                best = c
        return best


def _try_join(a, b):
    """两区间若能并成一段则返回合并结果，否则返回空。"""
    lo = a[0]
    if b[0] < lo:
        lo = b[0]
    hi = a[1]
    if b[1] > hi:
        hi = b[1]
    if a[0] <= b[1] and b[0] <= a[1]:
        return (lo, hi)
    return NONE


def _unique_sorted(values):
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    seen.sort()
    return seen
