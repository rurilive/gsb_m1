"""pathcover.covering：朴素有向无环图最小路径覆盖（改造前基线）。

有向图上的最小路径覆盖工具：点是任意可哈希对象，边有向，用有序对
集合表示，重复边只算一次，自环与空点当场拒掉。当前结果一律靠枚举
顶点划分得到：

- min_path_count()：枚举全部顶点划分成若干条路径的方案，逐方案检查
  每条路径里相邻两点是否真有边相连，取路径条数最少的方案
- min_path_cover()：同上，返回一个最小路径覆盖方案
- is_valid_cover(cover)：把给定覆盖也按同样的检查走一遍

点数一多，划分与排列的量就指数增长，这里只保证口径正确，不追求快。
拆点建二分图、求最大匹配那条路见任务描述。
"""

import itertools


class Erro(Exception):
    """pathcover 里所有可预期错误的基类。"""


class GraphError(Erro):
    """图本身不合法，比如自环或空点。"""


class NodeError(Erro):
    """引用了未在图中出现过的点。"""


class CoverError(Erro):
    """给出的路径覆盖不合法，比如漏点、重复点或用了不存在的边。"""


def _key(node):
    """把点压成可比较、可排序的表示，用来稳定枚举顺序。"""
    return type(node).__name__, repr(node)


class PathCoverer:
    """朴素有向图最小路径覆盖工具，结果一律靠枚举顶点划分得到。"""

    def __init__(self):
        self._nodes = []
        self._node_set = set()
        self._succ = {}
        self._pred = {}
        self._edges = set()
        self._last = None

    # -- 建图 -------------------------------------------------------------

    def add_edge(self, u, v):
        """加一条有向边 u 到 v，重复边只算一次，返回自身。"""
        if u is None or v is None:
            raise GraphError("边的两端都不能为空: %r, %r" % (u, v))
        if u == v:
            raise GraphError("自环不是合法边: %r" % (u,))
        self._register(u)
        self._register(v)
        self._succ[u].add(v)
        self._pred[v].add(u)
        self._edges.add((u, v))
        return self

    def add_node(self, node):
        """登记一个孤立点（没有任何边连到它），返回自身。"""
        if node is None:
            raise GraphError("点不能为空: %r" % (node,))
        self._register(node)
        return self

    def _register(self, node):
        if node not in self._node_set:
            self._node_set.add(node)
            self._nodes.append(node)
            self._succ[node] = set()
            self._pred[node] = set()

    # -- 读图 -------------------------------------------------------------

    @property
    def nodes(self):
        """全部点，按首次出现顺序。"""
        return list(self._nodes)

    def node_count(self):
        return len(self._nodes)

    def edges(self):
        """全部有向边，按两端稳定排序后给出。"""
        return sorted(self._edges, key=lambda e: (_key(e[0]), _key(e[1])))

    def edge_count(self):
        return len(self._edges)

    def has_edge(self, u, v):
        """从 u 到 v 是否有一条有向边，任一端没出现过就报错。"""
        if u not in self._node_set or v not in self._node_set:
            raise NodeError("图里没有这个点: %r, %r" % (u, v))
        return (u, v) in self._edges

    def successors(self, node):
        """某个点一步能到的点集合，点没出现过就报错。"""
        if node not in self._node_set:
            raise NodeError("图里没有这个点: %r" % (node,))
        return set(self._succ[node])

    def predecessors(self, node):
        """一步能到某个点的点集合，点没出现过就报错。"""
        if node not in self._node_set:
            raise NodeError("图里没有这个点: %r" % (node,))
        return set(self._pred[node])

    # -- 枚举求最小路径覆盖 -------------------------------------------------

    def _cover_key(self, cover):
        """把一个覆盖压成可比较的稳定表示：路径按起点排序后再逐条比。"""
        paths = sorted(
            (tuple(_key(v) for v in path) for path in cover),
            key=lambda p: p[0],
        )
        return tuple(paths)

    def _enumerate_best(self):
        """枚举全部顶点划分与排列，返回条数最少且字典序最小的覆盖。"""
        nodes = self._nodes
        n = len(nodes)
        if n == 0:
            return []
        best = None
        best_key = None
        for perm in itertools.permutations(range(n)):
            if n == 1:
                cut_iter = [0]
            else:
                cut_iter = range(1 << (n - 1))
            for cuts in cut_iter:
                blocks = []
                cur = [perm[0]]
                for i in range(1, n):
                    if (cuts >> (i - 1)) & 1:
                        blocks.append(cur)
                        cur = [perm[i]]
                    else:
                        cur.append(perm[i])
                blocks.append(cur)
                cover = [[nodes[x] for x in b] for b in blocks]
                valid = True
                for path in cover:
                    if len(path) > 1:
                        for i in range(len(path) - 1):
                            if (path[i], path[i + 1]) not in self._edges:
                                valid = False
                                break
                    if not valid:
                        break
                if not valid:
                    continue
                key = self._cover_key(cover)
                if best is None or (len(cover), key) < (len(best), best_key):
                    best = cover
                    best_key = key
        return best

    def min_path_count(self):
        """最小路径覆盖里的路径条数。"""
        self._last = self._enumerate_best()
        return len(self._last)

    def min_path_cover(self):
        """一个最小路径覆盖方案，写成若干条有序路径的表。"""
        self._last = self._enumerate_best()
        return [list(path) for path in self._last]

    def is_valid_cover(self, cover):
        """给定覆盖是否是这张图上的合法路径覆盖（不漏点、不重复、边真存在）。"""
        if cover is None:
            raise CoverError("覆盖不能为空")
        if not isinstance(cover, (list, tuple)):
            raise CoverError("覆盖要写成若干条路径的表")
        seen = []
        for path in cover:
            if not isinstance(path, (list, tuple)):
                raise CoverError("每条路径要写成点的表")
            if len(path) == 0:
                raise CoverError("路径不能是空的")
            for v in path:
                if v not in self._node_set:
                    raise NodeError("图里没有这个点: %r" % (v,))
                seen.append(v)
            for i in range(len(path) - 1):
                if (path[i], path[i + 1]) not in self._edges:
                    raise CoverError(
                        "这条路径上用了一条不存在的边: %r, %r" % (path[i], path[i + 1])
                    )
        if len(seen) != len(set(seen)):
            raise CoverError("覆盖里同一个点出现了不止一次")
        if set(seen) != self._node_set:
            raise CoverError("覆盖没有用上全部点")
        return True
