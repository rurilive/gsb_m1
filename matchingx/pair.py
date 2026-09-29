"""matchingx.pair：朴素二分匹配工具（改造前基线）。

左侧一组点，右侧一组点，边用对集合表示。add_edge 逐条加边，
is_perfect 与 max_pairs 都用回溯枚举全部匹配来得到答案，
最坏情形下枚举量随点数指数增长。
"""


class MatchingError(Exception):
    """匹配工具异常基类。"""


class UnknownPointError(MatchingError):
    """引用了未在图中出现过的点。"""


class NotMatchedError(MatchingError):
    """请求的左侧点当前没有配到任何右侧点。"""


class BrutePair:
    """朴素二分匹配：用回溯枚举求匹配。"""

    def __init__(self):
        self._edges = set()
        self._left = []
        self._left_set = set()
        self._right = []
        self._right_set = set()
        self._adj = {}
        self._matching = None

    def add_edge(self, left, right):
        if left is None or right is None:
            raise UnknownPointError("点不能为空")
        self._edges.add((left, right))
        if left not in self._left_set:
            self._left_set.add(left)
            self._left.append(left)
            self._adj[left] = set()
        if right not in self._right_set:
            self._right_set.add(right)
            self._right.append(right)
        self._adj[left].add(right)
        return self

    @property
    def left_points(self):
        return list(self._left)

    @property
    def right_points(self):
        return list(self._right)

    def edge_count(self):
        return len(self._edges)

    def neighbors(self, left):
        if left not in self._left_set:
            raise UnknownPointError(left)
        return set(self._adj[left])

    def _search(self):
        # 回溯枚举：每个左侧点轮流尝试配到一个尚未占用的右侧点，
        # 也允许不配，从而覆盖全部匹配组合。
        best = {}

        def rec(i, used, cur):
            nonlocal best
            if i == len(self._left):
                if len(cur) > len(best):
                    best = dict(cur)
                return
            l = self._left[i]
            for r in sorted(self._adj[l], key=repr):
                if r in used:
                    continue
                used.add(r)
                cur[l] = r
                rec(i + 1, used, cur)
                del cur[l]
                used.discard(r)
            rec(i + 1, used, cur)

        rec(0, set(), {})
        return best

    def max_pairs(self):
        self._matching = self._search()
        return len(self._matching)

    def is_perfect(self):
        self._matching = self._search()
        return len(self._matching) == len(self._left)

    def matched_to(self, left):
        if left not in self._left_set:
            raise UnknownPointError(left)
        if self._matching is None:
            raise MatchingError("尚未求出匹配方案")
        if left not in self._matching:
            raise NotMatchedError(left)
        return self._matching[left]
