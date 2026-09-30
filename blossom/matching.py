"""blossom.matching：朴素一般图匹配（改造前基线）。

一般图上的匹配工具：点是任意可哈希对象，边无向，用对集合表示，
重复边只算一次，自环与空点当场拒掉。当前所有结果都由回溯枚举驱动：

- max_matching_size()：枚举全部边组合，取两两不共点且条数最多的那种
- max_matching()：同上，返回一个最大匹配方案
- is_maximum(matching)：枚举全部匹配，把给定匹配的大小与真正最大值比较
- perfect_matching_exists()：最大匹配是否覆盖全部点

点数或边数一多，组合数就指数增长，这里只保证口径正确，不追求快。
带花树增广那条路见任务描述。
"""


class Erro(Exception):
    """blossom 里所有可预期错误的基类。"""


class GraphError(Erro):
    """图本身不合法，比如自环或空点。"""


class NodeError(Erro):
    """引用了未在图中出现过的点。"""


class MatchError(Erro):
    """给出的匹配不合法，比如用了不存在的边或共用了点。"""


class NotMatchedError(Erro):
    """请求的点当前没有配到任何点。"""


def _key(node):
    """把点压成可比较、可排序的表示，用来稳定枚举顺序。"""
    return type(node).__name__, repr(node)


class GraphMatcher:
    """朴素一般图匹配工具，结果一律靠回溯枚举得到。"""

    def __init__(self):
        self._nodes = []
        self._node_set = set()
        self._adj = {}
        self._edges = set()
        self._last = None

    # -- 建图 -------------------------------------------------------------

    def add_edge(self, u, v):
        """加一条无向边，重复边只算一次，返回自身。"""
        if u is None or v is None:
            raise GraphError("边的两端都不能为空: %r, %r" % (u, v))
        if u == v:
            raise GraphError("自环不是合法边: %r" % (u,))
        self._register(u)
        self._register(v)
        self._adj[u].add(v)
        self._adj[v].add(u)
        self._edges.add(self._norm(u, v))
        return self

    def _register(self, node):
        if node not in self._node_set:
            self._node_set.add(node)
            self._nodes.append(node)
            self._adj[node] = set()

    @staticmethod
    def _norm(u, v):
        """把一条边的两端按稳定顺序摆好，便于去重与排序。"""
        return (u, v) if _key(u) <= _key(v) else (v, u)

    # -- 读图 -------------------------------------------------------------

    @property
    def nodes(self):
        """全部点，按首次出现顺序。"""
        return list(self._nodes)

    def node_count(self):
        return len(self._nodes)

    def edges(self):
        """全部边，按两端稳定排序后给出。"""
        return sorted(self._edges, key=lambda e: (_key(e[0]), _key(e[1])))

    def edge_count(self):
        return len(self._edges)

    def has_edge(self, u, v):
        """两点之间是否有边，任一端没出现过就报错。"""
        if u not in self._node_set or v not in self._node_set:
            raise NodeError("图里没有这个点: %r, %r" % (u, v))
        return self._norm(u, v) in self._edges

    def neighbors(self, node):
        """某个点连到的点集合，点没出现过就报错。"""
        if node not in self._node_set:
            raise NodeError("图里没有这个点: %r" % (node,))
        return set(self._adj[node])

    # -- 枚举求匹配 -------------------------------------------------------

    def _pair_keys(self, pairs):
        return tuple((_key(u), _key(v)) for u, v in pairs)

    def _enumerate_best(self):
        """回溯枚举全部边组合，返回条数最多且字典序最小的匹配。"""
        edge_list = self.edges()
        best = []

        def walk(i, used, chosen):
            nonlocal best
            if i == len(edge_list):
                if len(chosen) > len(best):
                    best = list(chosen)
                elif len(chosen) == len(best) and chosen:
                    if self._pair_keys(chosen) < self._pair_keys(best):
                        best = list(chosen)
                return
            walk(i + 1, used, chosen)
            u, v = edge_list[i]
            if u not in used and v not in used:
                used.add(u)
                used.add(v)
                chosen.append((u, v))
                walk(i + 1, used, chosen)
                chosen.pop()
                used.discard(u)
                used.discard(v)

        walk(0, set(), [])
        return best

    @staticmethod
    def _as_dict(pairs):
        out = {}
        for u, v in pairs:
            out[u] = v
            out[v] = u
        return out

    def max_matching_size(self):
        """最大匹配的边数。"""
        self._last = self._enumerate_best()
        return len(self._last)

    def max_matching(self):
        """一个最大匹配方案，写成点到处处的映射，两端都出现。"""
        self._last = self._enumerate_best()
        return self._as_dict(self._last)

    def matched_to(self, node):
        """回查某个点在最近一次求出的最大匹配里配到谁。"""
        if node not in self._node_set:
            raise NodeError("图里没有这个点: %r" % (node,))
        if self._last is None:
            self._last = self._enumerate_best()
        for u, v in self._last:
            if u == node:
                return v
            if v == node:
                return u
        raise NotMatchedError("这个点没有配到任何点: %r" % (node,))

    def is_maximum(self, matching):
        """给定匹配是否达到了最大匹配的条数。"""
        if matching is None:
            raise MatchError("匹配不能为空")
        if not isinstance(matching, dict):
            raise MatchError("匹配要写成点到处处的映射")
        for u in matching:
            if u not in self._node_set:
                raise NodeError("图里没有这个点: %r" % (u,))
        for u, v in matching.items():
            if v not in self._node_set:
                raise NodeError("图里没有这个点: %r" % (v,))
            if u == v:
                raise MatchError("匹配里不能把点配到自己: %r" % (u,))
            if self._norm(u, v) not in self._edges:
                raise MatchError("匹配用了一条不存在的边: %r, %r" % (u, v))
            if matching.get(v) != u:
                raise MatchError("匹配必须成对出现且互指: %r, %r" % (u, v))
        return len(matching) // 2 == self.max_matching_size()

    def perfect_matching_exists(self):
        """是否存在覆盖全部点的完美匹配。"""
        return len(self._nodes) % 2 == 0 and 2 * self.max_matching_size() == len(
            self._nodes
        )
