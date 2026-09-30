"""改造前的朴素实现：Reroot 对每个结点单独当根重算一遍。

树的根固定为编号 0，边以无向对给出。当前对外提供三类以某点为根的量：

- 子树大小：以该点为根时，每个结点所在子树的结点个数；
- 距离之和：该点到树上其它所有点的距离之和；
- 最深子树高度：以该点为根时，从该点出发能走到的最远步数。

朴素口径：对每个结点 ``r``，都把 ``r`` 单独当作根，从 ``r`` 出发重新
做一次完整的深搜，现场求出以 ``r`` 为根时的父子关系、子树大小与各种
聚合量。求全部结点的答案时，每个结点都要重走整棵树，总代价随结点数
反复累加，退到平方量级；树一深、结点一多就跑不动，也没有一处能在固定
输入上把结果与另一条独立口径逐项对照。
"""

__all__ = [
    "Reroot",
    "RerootError",
    "RerootInputError",
    "UnknownNodeError",
    "DisconnectedError",
]


class RerootError(Exception):
    """本模块所有异常的基类。"""


class RerootInputError(RerootError):
    """结点数或边的取值不合法。"""


class UnknownNodeError(RerootError):
    """查询引用了不在树中的结点编号。"""


class DisconnectedError(RerootError):
    """给出的边没有连成一棵覆盖全部结点的树。"""


class Reroot:
    """载入一棵无向树，给出以任意点为根时的聚合量。

    邻接表保存在实例上，模块级不持有任何可变状态；同一实例对固定输入
    重复查询结果一致。
    """

    def __init__(self):
        self._n = 0
        self._adj = []
        self._loaded = False

    # ------------------------------------------------------------------
    # 载入与校验
    # ------------------------------------------------------------------
    def load(self, n, edges):
        """载入结点数为 n 的树，边为 (u, v) 无序点对列表。

        合法的树恰好有 n 减 1 条边，且这些边把全部结点连成一棵。
        """
        if not isinstance(n, int) or n <= 0:
            raise RerootInputError("结点数必须为正整数: %r" % (n,))
        for e in edges:
            if not isinstance(e, (tuple, list)) or len(e) != 2:
                raise RerootInputError("边必须是两点对: %r" % (e,))
            for x in e:
                if not isinstance(x, int) or x < 0 or x >= n:
                    raise RerootInputError("边端点越界: %r" % (x,))
        if len(edges) != n - 1:
            raise DisconnectedError("树的边数应为结点数减一: %d" % (len(edges),))
        adj = [[] for _ in range(n)]
        for u, v in edges:
            adj[u].append(v)
            adj[v].append(u)
        # 与查询无关的稳定顺序: 邻接表按编号升序，保证遍历次序确定
        for row in adj:
            row.sort()
        # 以 0 为根走一次，确认全部结点连通
        seen = [False] * n
        seen[0] = True
        stack = [0]
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if not seen[w]:
                    seen[w] = True
                    stack.append(w)
        if not all(seen):
            raise DisconnectedError("给出的边没有连成一棵覆盖全部结点的树")
        self._n = n
        self._adj = adj
        self._loaded = True

    def _check_loaded(self):
        if not self._loaded:
            raise RerootInputError("尚未载入任何树")

    def _check_node(self, u):
        if not isinstance(u, int) or u < 0 or u >= self._n:
            raise UnknownNodeError("未知结点编号: %r" % (u,))

    # ------------------------------------------------------------------
    # 朴素口径: 每个根都从头深搜一遍
    # ------------------------------------------------------------------
    def _dfs_from(self, root):
        """从 root 出发做一次完整深搜，返回父子关系与后序序列。

        结点按邻接表中的先序入栈，父结点先于子结点确定，次序确定可复现。
        """
        parent = [-1] * self._n
        order = []
        seen = [False] * self._n
        seen[root] = True
        stack = [root]
        while stack:
            u = stack.pop()
            order.append(u)
            for w in self._adj[u]:
                if not seen[w]:
                    seen[w] = True
                    parent[w] = u
                    stack.append(w)
        return parent, order

    def _subtree_sizes(self, root):
        """以 root 为根时每个结点的子树大小。"""
        parent, order = self._dfs_from(root)
        size = [1] * self._n
        for u in reversed(order):
            p = parent[u]
            if p != -1:
                size[p] += size[u]
        return size

    def _depths(self, root):
        """以 root 为根时从 root 出发到各结点的步数，后序求。"""
        parent, order = self._dfs_from(root)
        depth = [0] * self._n
        for u in order:
            p = parent[u]
            if p != -1:
                depth[u] = depth[p] + 1
        return depth

    # ------------------------------------------------------------------
    # 对外口径
    # ------------------------------------------------------------------
    def subtree_sizes(self, root):
        """以 root 为根时，返回结点编号到其子树大小的映射。"""
        self._check_loaded()
        self._check_node(root)
        size = self._subtree_sizes(root)
        return {u: size[u] for u in range(self._n)}

    def distance_sum(self, root):
        """返回 root 到树上其它所有点的距离之和。"""
        self._check_loaded()
        self._check_node(root)
        depth = self._depths(root)
        return sum(depth)

    def all_distance_sums(self):
        """逐结点单独当根，返回每个点到其它所有点的距离之和。"""
        self._check_loaded()
        return {u: self.distance_sum(u) for u in range(self._n)}

    def deepest_subtree(self, root):
        """以 root 为根时从 root 出发的最远步数，即树高。"""
        self._check_loaded()
        self._check_node(root)
        depth = self._depths(root)
        return max(depth)

    def all_deepest_subtrees(self):
        """逐结点单独当根，返回每个结点出发的最远步数。"""
        self._check_loaded()
        return {u: self.deepest_subtree(u) for u in range(self._n)}

    def node_count(self):
        """返回结点个数。"""
        self._check_loaded()
        return self._n

    def visit_count(self):
        """返回逐根单独深搜口径下访问结点的总次数。

        朴素口径下，结点 r 的答案要把整棵树走一遍，故总次数是
        结点数乘以每棵树的大小，即结点数的平方。
        """
        self._check_loaded()
        total = 0
        for r in range(self._n):
            total += len(self._dfs_from(r)[1])
        return total
