"""FlatForest: 朴素动态森林（改造前基线）。

用邻接集合维护一组带点权的节点与它们之间的边，所有操作都是当场遍历：

- add_node(u)：登记一个孤立节点，权值默认 0
- link(u, v)：在当前森林里连一条 u 与 v 的边
- cut(u, v)：断掉 u 与 v 之间已有的那条边
- neighbors(u)：返回 u 当前邻居的下标集合副本
- has_edge(u, v)：直接看邻接表里有没有这条边
- connected(u, v)：从 u 出发做一次深度优先，看 v 是否可达
- path_sum(u, v)：先找一条路径，再把路径上的点权逐个加起来
- set_weight(u, x) / weight(u)：点权读写
- component_count()：每次从头对整片森林数一遍连通分量

节点用不重复的整数 id 标识。边用无向邻接集合维护，连边是双向登记。
每次操作都可能把整棵树走一遍，连边断边一多、长链一长就退化成线性。
"""


class LctError(Exception):
    """lctlib 里所有可预期错误的基类。"""


class NoSuchNode(LctError):
    """引用了不存在的节点 id。"""


class NoSuchEdge(LctError):
    """引用了一条当前不存在的边。"""


class FlatForest:
    """动态森林：邻接集合加当场遍历的连通、路径与分量统计。"""

    def __init__(self):
        """建一片空森林。"""
        self._adj = {}
        self._weight = {}

    # -- 内部校验 ---------------------------------------------------------

    def _require(self, u):
        if u not in self._adj:
            raise NoSuchNode("不存在的节点: %r" % (u,))
        return u

    # -- 结构维护 ---------------------------------------------------------

    def add_node(self, u):
        """登记一个孤立节点；重复登记是错的，就地快速失败。"""
        if u in self._adj:
            raise LctError("节点已存在: %r" % (u,))
        self._adj[u] = set()
        self._weight[u] = 0
        return u

    def nodes(self):
        """返回全部节点 id，顺序按登记顺序。"""
        return list(self._adj)

    def neighbors(self, u):
        """返回 u 当前邻居的下标集合的副本。"""
        self._require(u)
        return set(self._adj[u])

    def has_edge(self, u, v):
        """直接看邻接表里有没有这条无向边。"""
        self._require(u)
        self._require(v)
        return v in self._adj[u]

    def edge_count(self):
        """当前边的条数（无向边只算一次）。"""
        total = 0
        for u in self._adj:
            total += len(self._adj[u])
        return total // 2

    def link(self, u, v):
        """连一条 u 与 v 的边。

        约定很朴素：两个节点都得在、不能是自己连自己、不能与已有的边重复，
        而且连上以后不能成环，也就是两边原本必须不连通。任何一条不满足都
        就地快速失败，绝不悄悄忽略。
        """
        self._require(u)
        self._require(v)
        if u == v:
            raise LctError("不允许自环: %r" % (u,))
        if v in self._adj[u]:
            raise LctError("边已存在: %r-%r" % (u, v))
        if self.connected(u, v):
            raise LctError("连边会成环: %r-%r" % (u, v))
        self._adj[u].add(v)
        self._adj[v].add(u)
        return True

    def cut(self, u, v):
        """断掉 u 与 v 之间已有的那条边；边不存在就失败。"""
        self._require(u)
        self._require(v)
        if v not in self._adj[u]:
            raise NoSuchEdge("待断的边不存在: %r-%r" % (u, v))
        self._adj[u].discard(v)
        self._adj[v].discard(u)
        return True

    # -- 点权 -------------------------------------------------------------

    def weight(self, u):
        """返回 u 的点权。"""
        self._require(u)
        return self._weight[u]

    def set_weight(self, u, x):
        """设置 u 的点权。"""
        self._require(u)
        self._weight[u] = x

    # -- 当场遍历的查询 ---------------------------------------------------

    def _dfs(self, start):
        """从 start 出发做一次深度优先，返回访问到的节点集合。"""
        self._require(start)
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in self._adj[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def connected(self, u, v):
        """连通性：从 u 做一次深度优先，看能不能走到 v。"""
        self._require(u)
        self._require(v)
        if u == v:
            return True
        return v in self._dfs(u)

    def component_count(self):
        """连通分量个数：从头把整片森林逐节点数一遍。"""
        seen = set()
        count = 0
        for start in self._adj:
            if start in seen:
                continue
            count += 1
            seen |= self._dfs(start)
        return count

    def _find_path(self, u, v):
        """在当前的树里找一条 u 到 v 的路径，返回节点序列；找不到返回空列表。"""
        self._require(u)
        self._require(v)
        if u == v:
            return [u]
        parent = {u: None}
        stack = [u]
        while stack:
            cur = stack.pop()
            if cur == v:
                break
            for nxt in self._adj[cur]:
                if nxt not in parent:
                    parent[nxt] = cur
                    stack.append(nxt)
        if v not in parent:
            return []
        path = []
        cur = v
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        return path

    def path_sum(self, u, v):
        """路径点权和：先找一条路径，再把路径上的点权逐个加起来。

        u 与 v 不连通时直接失败。
        """
        path = self._find_path(u, v)
        if not path:
            raise LctError("两点不连通: %r-%r" % (u, v))
        total = 0
        for node in path:
            total += self._weight[node]
        return total

    def path_add(self, u, v, delta):
        """路径点权加：把路径上每个节点的点权逐个加上增量，返回受影响的节点序列。"""
        path = self._find_path(u, v)
        if not path:
            raise LctError("两点不连通: %r-%r" % (u, v))
        for node in path:
            self._weight[node] += delta
        return path

    def subtree_sum(self, u, root):
        """给定根 root 时，以 u 为根的子树点权和。

        做法很直白：先以 root 为起点把整棵树的父子关系定出来，再从 u 出发
        只往子节点那一侧走，把 u 下面那半棵树逐节点走一遍再加起来。
        u 与 root 不连通时直接失败。
        """
        self._require(u)
        self._require(root)
        parent = {root: None}
        stack = [root]
        while stack:
            cur = stack.pop()
            for nxt in self._adj[cur]:
                if nxt not in parent:
                    parent[nxt] = cur
                    stack.append(nxt)
        if u not in parent:
            raise LctError("两点不连通: %r-%r" % (u, root))
        seen = set()
        stack = [u]
        total = 0
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            total += self._weight[cur]
            for nxt in self._adj[cur]:
                if nxt != parent[cur] and nxt not in seen:
                    stack.append(nxt)
        return total
