"""朴素动态森林 Dtree：改造前的基线实现。

用无向邻接集合维护一组带点权的节点与它们之间的边，所有操作都当场重扫：

- add_node(u)：登记一个孤立节点，点权默认 0
- link(u, v) / cut(u, v)：连边与断边，连边拒绝自环、重复边与成环
- neighbors(u) / has_edge(u, v) / edge_count()：邻接视图
- connected(u, v)：从一端做一次深度优先判断连通
- component_count()：每次从头把整片森林数一遍连通分量
- path_sum(u, v) / path_max(u, v)：先把一条路径找出来，再沿路径逐节点求和或取最值
- path_add(u, v, delta)：沿路径逐节点改写点权，返回被改动的节点序列
- make_root(u)：以 u 为根，把 u 所在那棵树的根标记整体重扫一遍
- component_root(u)：读回 u 所在树当前记录的根
- subtree_sum(u, root)：给定根时把 u 的子树逐节点走一遍再加
- set_weight(u, x) / weight(u)：点权读写
- reset_cost() / last_cost()：上一次操作看过的节点数，用来看逐次重扫的代价

节点用不重复的整数 id 标识，边用无向邻接集合维护。每次查询与换根都可能把
整棵树走一遍，操作一多、链一长就退化成线性。异常统一继承 DtreeError。
"""


class DtreeError(Exception):
    """lctx 里所有可预期错误的基类。"""


class NoSuchNode(DtreeError):
    """引用了不存在的节点 id。"""


class NoSuchEdge(DtreeError):
    """引用了一条当前不存在的边。"""


class Dtree:
    """动态森林：邻接集合加当场遍历的连通、路径与子树统计。"""

    def __init__(self):
        """建一片空森林。"""
        self._adj = {}
        self._weight = {}
        self._root = {}
        self._cost = 0

    # -- 代价计数 ---------------------------------------------------------

    def reset_cost(self):
        """把操作代价计数清零。"""
        self._cost = 0

    def last_cost(self):
        """返回上一次操作看过的节点数。"""
        return self._cost

    def _touch(self):
        """记一次节点访问。"""
        self._cost += 1

    # -- 内部校验 ---------------------------------------------------------

    def _require(self, u):
        if u not in self._adj:
            raise NoSuchNode("不存在的节点: %r" % (u,))
        return u

    # -- 结构维护 ---------------------------------------------------------

    def add_node(self, u):
        """登记一个孤立节点；重复登记是错的，就地快速失败。"""
        if u in self._adj:
            raise DtreeError("节点已存在: %r" % (u,))
        self._adj[u] = set()
        self._weight[u] = 0
        self._root[u] = u
        return u

    def nodes(self):
        """返回全部节点 id，顺序按登记顺序。"""
        return list(self._adj)

    def neighbors(self, u):
        """返回 u 当前邻居集合的副本。"""
        self._require(u)
        return set(self._adj[u])

    def has_edge(self, u, v):
        """直接看邻接表里有没有这条无向边。"""
        self._require(u)
        self._require(v)
        return v in self._adj[u]

    def edge_count(self):
        """当前边的条数，无向边只算一次。"""
        total = 0
        for u in self._adj:
            total += len(self._adj[u])
        return total // 2

    def link(self, u, v):
        """连一条 u 与 v 的边，两边原本必须属于不同的两棵树。

        自己连自己、与已有的边重复、连上会成环，任何一条都就地快速失败，
        绝不悄悄忽略。
        """
        self._require(u)
        self._require(v)
        if u == v:
            raise DtreeError("不允许自环: %r" % (u,))
        if v in self._adj[u]:
            raise DtreeError("边已存在: %r-%r" % (u, v))
        if self.connected(u, v):
            raise DtreeError("连边会成环: %r-%r" % (u, v))
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

    # -- 当场遍历的连通与分量 ---------------------------------------------

    def _reach(self, start):
        """从 start 出发做一次深度优先，返回访问到的节点集合。"""
        self._require(start)
        self._touch()
        seen = {start}
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in self._adj[cur]:
                if nxt not in seen:
                    self._touch()
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def connected(self, u, v):
        """连通性：从 u 做一次深度优先，看能不能走到 v。"""
        self._require(u)
        self._require(v)
        if u == v:
            return True
        return v in self._reach(u)

    def component_count(self):
        """连通分量个数：从头把整片森林逐节点数一遍。"""
        seen = set()
        count = 0
        for start in self._adj:
            if start in seen:
                continue
            count += 1
            seen |= self._reach(start)
        return count

    # -- 换根 -------------------------------------------------------------

    def component_root(self, u):
        """返回 u 所在那棵树当前记录的根。"""
        self._require(u)
        return self._root[u]

    def make_root(self, u):
        """以 u 为根：把 u 所在那棵树的父子关系整体重扫一遍，重标根。

        做法是把 u 可达的节点全部走一遍，逐个把记录的根改成 u；另一棵树
        的根标记不受影响。换一次根就是一次整树遍历。
        """
        self._require(u)
        for node in self._reach(u):
            self._root[node] = u
        return u

    # -- 当场遍历的路径查询 -------------------------------------------------

    def _find_path(self, u, v):
        """在当前的森林里找一条 u 到 v 的路径，返回节点序列；找不到返回空列表。"""
        self._require(u)
        self._require(v)
        self._touch()
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
                    self._touch()
                    parent[nxt] = cur
                    stack.append(nxt)
        if v not in parent:
            return []
        path = []
        cur = v
        while cur is not None:
            self._touch()
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        return path

    def path_sum(self, u, v):
        """路径点权和：先找一条路径，再把路径上的点权逐个加起来。"""
        path = self._find_path(u, v)
        if not path:
            raise DtreeError("两点不连通: %r-%r" % (u, v))
        total = 0
        for node in path:
            total += self._weight[node]
        return total

    def path_max(self, u, v):
        """路径点权最大值：先找一条路径，再沿路径逐个比大小。"""
        path = self._find_path(u, v)
        if not path:
            raise DtreeError("两点不连通: %r-%r" % (u, v))
        best = self._weight[path[0]]
        for node in path[1:]:
            if self._weight[node] > best:
                best = self._weight[node]
        return best

    def path_add(self, u, v, delta):
        """路径点权加：把路径上每个节点的点权逐个加上增量，返回受影响的节点序列。"""
        path = self._find_path(u, v)
        if not path:
            raise DtreeError("两点不连通: %r-%r" % (u, v))
        for node in path:
            self._weight[node] += delta
        return path

    def subtree_sum(self, u, root):
        """给定根 root 时，以 u 为根的子树点权和。

        做法很直白：先以 root 为起点把整棵树的父子关系定出来，再从 u 出发只
        往子节点那一侧走，把 u 下面那半棵树逐节点走一遍再加起来。u 与 root
        不连通时直接失败。
        """
        self._require(u)
        self._require(root)
        self._touch()
        parent = {root: None}
        stack = [root]
        while stack:
            cur = stack.pop()
            for nxt in self._adj[cur]:
                if nxt not in parent:
                    self._touch()
                    parent[nxt] = cur
                    stack.append(nxt)
        if u not in parent:
            raise DtreeError("两点不连通: %r-%r" % (u, root))
        seen = set()
        stack = [u]
        total = 0
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            self._touch()
            seen.add(cur)
            total += self._weight[cur]
            for nxt in self._adj[cur]:
                if nxt != parent[cur] and nxt not in seen:
                    stack.append(nxt)
        return total
