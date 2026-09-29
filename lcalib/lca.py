"""最近公共祖先的朴素实现（改造前基线）。

用父子边建有根树，每次查询都沿父指针逐层上爬：
求深度要一路数到根，求最近公共祖先要先把较深的一侧爬到同层，
再让两侧一起上爬，求距离与祖先关系同样靠逐层上爬完成。
深链上单次查询的代价随链长线性增长，批量查询里同一个节点
被反复重爬，没有任何预处理、倍增表或欧拉序。这里只有这一条
逐层上爬的路径。
"""


class LcaError(Exception):
    """本包所有面向使用者的异常的共同基类。"""


class LcaNodeError(LcaError):
    """节点未知、树根缺失或父子边自相矛盾时抛出。"""


class NaiveLca:
    """朴素最近公共祖先。

    用一组有向的父子边描述一棵有根树，节点取任意可哈希值。
    查询时逐层上爬：``parent`` 返回父节点，``depth`` 数到根，
    ``lca`` 先对齐深度再一起上爬，``dist`` 由深度与最近公共祖先
    得到，``is_ancestor`` 逐个上爬比对。非法节点一律快速失败，
    不悄悄修正。
    """

    def __init__(self, edges, root=None):
        """用父子边序列建树。

        ``edges`` 是若干 ``(父, 子)`` 对。``root`` 缺省时自动推断：
        在出现过的节点里取唯一没有父节点的那个；若没有这样的节点
        或有多个，抛 ``LcaNodeError``。
        """
        self._parent = {}
        self._children = {}
        for edge in edges:
            try:
                p, c = edge
            except (TypeError, ValueError):
                raise LcaNodeError("父子边必须是二元组: {!r}".format(edge))
            if p == c:
                raise LcaNodeError("节点不能是自己的父节点: {!r}".format(p))
            if c in self._parent:
                raise LcaNodeError("节点有多个父节点: {!r}".format(c))
            self._parent[c] = p
            self._parent.setdefault(p, None)
            self._children.setdefault(p, []).append(c)
            self._children.setdefault(c, [])
        if root is None:
            roots = [n for n, p in self._parent.items() if p is None]
            if len(roots) != 1:
                raise LcaNodeError("无法唯一确定树根: {!r}".format(roots))
            root = roots[0]
        elif root not in self._parent:
            if self._parent:
                raise LcaNodeError("根节点不在树中: {!r}".format(root))
            self._parent[root] = None
            self._children[root] = []
        elif self._parent[root] is not None:
            raise LcaNodeError("指定的根节点还有父节点: {!r}".format(root))
        if self._has_cycle(root):
            raise LcaNodeError("父子边构成了环")
        self._root = root

    # ---- 基本信息 ------------------------------------------------------

    @property
    def root(self):
        """树根。"""
        return self._root

    def nodes(self):
        """全部节点的列表，顺序与内部登记一致。"""
        return list(self._parent)

    def __len__(self):
        """节点总数。"""
        return len(self._parent)

    def __contains__(self, u):
        return u in self._parent

    def children(self, u):
        """节点 u 的孩子列表（按登记顺序）。"""
        self._require(u)
        return list(self._children[u])

    # ---- 逐层上爬的查询 ------------------------------------------------

    def parent(self, u):
        """返回 u 的父节点；根返回 None。"""
        self._require(u)
        return self._parent[u]

    def depth(self, u):
        """返回 u 的深度（根为 0），沿父指针一路数上去。"""
        self._require(u)
        d = 0
        cur = u
        while self._parent[cur] is not None:
            cur = self._parent[cur]
            d += 1
        return d

    def lca(self, u, v):
        """返回 u 与 v 的最近公共祖先。

        先把较深者沿父指针爬到与较浅者同层，再让两侧同步上爬，
        直到相遇。每一步都逐层走。
        """
        self._require(u)
        self._require(v)
        a, b = u, v
        da, db = self.depth(a), self.depth(b)
        while da > db:
            a = self._parent[a]
            da -= 1
        while db > da:
            b = self._parent[b]
            db -= 1
        while a != b:
            a = self._parent[a]
            b = self._parent[b]
        return a

    def dist(self, u, v):
        """返回 u 与 v 之间的边数（路径长度）。"""
        self._require(u)
        self._require(v)
        w = self.lca(u, v)
        return self.depth(u) + self.depth(v) - 2 * self.depth(w)

    def is_ancestor(self, u, v):
        """u 是否为 v 的祖先（节点是其自身的祖先）。"""
        self._require(u)
        self._require(v)
        cur = v
        while cur is not None:
            if cur == u:
                return True
            cur = self._parent[cur]
        return False

    def query_many(self, queries):
        """对一批 (u, v) 逐个求最近公共祖先，返回结果列表。

        这里只是把单次查询循环一遍，每个查询都各自从零逐层上爬，
        并没有共享任何预处理。
        """
        out = []
        for u, v in queries:
            out.append(self.lca(u, v))
        return out

    # ---- 内部 ----------------------------------------------------------

    def _require(self, u):
        if u not in self._parent:
            raise LcaNodeError("未知节点: {!r}".format(u))

    def _has_cycle(self, root):
        seen = {root}
        stack = [root]
        while stack:
            cur = stack.pop()
            for child in self._children[cur]:
                if child in seen:
                    return True
                seen.add(child)
                stack.append(child)
        return len(seen) != len(self._parent)
