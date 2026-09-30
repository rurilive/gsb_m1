"""改造前的朴素实现：ReachGraph 以邻接表存有向图，提供两两可达判断。

邻接表以字典保存，键是节点，值是该节点指向的邻居列表，列表保留插入顺序，
因此对同一张图、同一段插入序列，遍历顺序是完全确定的。节点本身只要求可
哈希，本模块不解释节点含义。

朴素口径有两个突出特征。其一，reachable 每次都从起点重新做一次深度优先
搜索，只回答单点可达，不缓存任何中间结果。其二，凡是涉及互达或同分量的
问题，都要正反各跑一遍遍历：same_component 先判 u 到 v 再判 v 到 u，
bidirectional 同理。这样每问一对点就要跑两遍遍历，分量相关的信息只能靠
成对询问拼出来，问遍所有点对时整体代价会迅速膨胀。
"""

__all__ = [
    "ReachGraph",
    "SccError",
    "UnknownNodeError",
    "GraphError",
]


class SccError(Exception):
    """本模块所有异常的基类。"""


class UnknownNodeError(SccError):
    """引用了图中不存在的节点。"""


class GraphError(SccError):
    """图的结构或用法有误。"""


class ReachGraph:
    """朴素有向图，支持加边、查询邻居、单点可达与两两互达判断。

    邻接表保存在实例上，模块级不持有任何可变状态，因此同一实例重复跑
    固定序列结果一致。节点以可哈希对象标识，非法节点一律快速失败。
    """

    def __init__(self):
        # 节点 -> 邻居列表，列表保留插入顺序以固定遍历次序
        self._adj = {}

    # ------------------------------------------------------------------
    # 节点的建立与查询
    # ------------------------------------------------------------------
    def add_node(self, node):
        """把一个节点加入图中；已存在则保持其邻居不变。"""
        if node not in self._adj:
            self._adj[node] = []
        return node

    def add_edge(self, u, v):
        """加入一条从 u 指向 v 的有向边，并确保两端节点存在。

        平行边与自环都原样保留，不去重、不拒绝，因为朴素口径把邻接表
        当作边上事实的直接记录。
        """
        if u not in self._adj:
            raise UnknownNodeError("边的起点不在图中: %r" % (u,))
        if v not in self._adj:
            raise UnknownNodeError("边的终点不在图中: %r" % (v,))
        self._adj[u].append(v)
        return self

    def has_node(self, node):
        """判断节点是否在图中。"""
        return node in self._adj

    def nodes(self):
        """按插入顺序返回全部节点。"""
        return list(self._adj.keys())

    def edges(self):
        """按节点插入顺序、邻居插入顺序返回全部有向边。"""
        result = []
        for u, nbrs in self._adj.items():
            for v in nbrs:
                result.append((u, v))
        return result

    def neighbors(self, u):
        """返回 u 的邻居列表副本，保持插入顺序。"""
        self._check(u)
        return list(self._adj[u])

    def degree(self, u):
        """返回 u 的出度，即其邻居条目数（平行边与自环计入）。"""
        self._check(u)
        return len(self._adj[u])

    def size(self):
        """返回节点个数。"""
        return len(self._adj)

    def edge_count(self):
        """返回有向边条目数（平行边与自环计入）。"""
        total = 0
        for nbrs in self._adj.values():
            total += len(nbrs)
        return total

    # ------------------------------------------------------------------
    # 朴素可达判断
    # ------------------------------------------------------------------
    def reachable(self, u, v):
        """判断是否存在从 u 到 v 的有向路径，从 u 做一次深度优先搜索。

        单独一次遍历，只回答这一对点，不缓存访问过的集合。
        """
        self._check(u)
        self._check(v)
        if u == v:
            return True
        seen = {u}
        stack = [u]
        while stack:
            cur = stack.pop()
            for nxt in self._adj[cur]:
                if nxt == v:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return False

    def same_component(self, u, v):
        """判断 u 与 v 是否互相可达，正反各做一遍遍历。"""
        self._check(u)
        self._check(v)
        return self.reachable(u, v) and self.reachable(v, u)

    def bidirectional(self, u, v):
        """判断是否同时存在 u 到 v 与 v 到 u 的路径，正反各做一遍遍历。"""
        self._check(u)
        self._check(v)
        return self.reachable(u, v) and self.reachable(v, u)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _check(self, node):
        if node not in self._adj:
            raise UnknownNodeError("节点不在图中: %r" % (node,))
