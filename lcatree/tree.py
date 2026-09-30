"""有根树的朴素实现：一切查询都靠沿父指针逐级上溯。

每个查询各自从结点出发一步步走到根，把途经结点按顺序记下来，
再从头逐项比对，因此查询一多、树一深就会很慢；结果正确。
"""


class TreeError(Exception):
    """本模块所有异常的基类。"""


class NodeNotFoundError(TreeError):
    """查询里出现了不在本树中的结点编号。"""


class InvalidTreeError(TreeError):
    """树的结构不合法，例如不连通、多个根或存在环。"""


class Tree(object):
    """一棵有根树，用父指针表示。

    parents 为字典，键是每一个结点编号，值是它的父结点编号；
    根结点的父结点记作 None。构造时会把结构校验一遍。
    """

    def __init__(self, parents):
        if not isinstance(parents, dict):
            raise InvalidTreeError("parents 必须是字典")
        if not parents:
            raise InvalidTreeError("树至少需要一个结点")
        self._parents = dict(parents)
        self._validate()

    def _validate(self):
        roots = []
        for node in self._parents:
            parent = self._parents[node]
            if parent is None:
                roots.append(node)
            elif parent not in self._parents:
                raise InvalidTreeError("父结点 %r 不在树中" % (parent,))
        if len(roots) != 1:
            raise InvalidTreeError("有根树必须恰好有一个根，实际有 %d 个" % len(roots))
        # 从每个结点上溯，必须在有限步内到根，否则说明有环。
        for node in self._parents:
            seen = set()
            cur = node
            while cur is not None:
                if cur in seen:
                    raise InvalidTreeError("从结点 %r 上溯出现环" % (node,))
                seen.add(cur)
                cur = self._parents[cur]
        self._root = roots[0]

    @property
    def root(self):
        return self._root

    def nodes(self):
        """返回全部结点编号的升序列表。"""
        return sorted(self._parents.keys())

    def _require(self, node):
        if node not in self._parents:
            raise NodeNotFoundError("结点 %r 不在树中" % (node,))

    def path_to_root(self, node):
        """从 node 一路沿父指针走到根，返回含 node 与根的列表。"""
        self._require(node)
        out = []
        cur = node
        while cur is not None:
            out.append(cur)
            cur = self._parents[cur]
        return out

    def depth(self, node):
        """结点深度，根为 0；靠沿父指针逐级上溯数步数。"""
        return len(self.path_to_root(node)) - 1

    def is_ancestor(self, ancestor, node):
        """ancestor 是否为 node 的祖先或就是它本身。靠逐级上溯判断。"""
        self._require(ancestor)
        self._require(node)
        cur = node
        while cur is not None:
            if cur == ancestor:
                return True
            cur = self._parents[cur]
        return False

    def lca(self, u, v):
        """最近公共祖先：两条到根的路径自根端逐项比对，最深的公共后缀就是答案。"""
        self._require(u)
        self._require(v)
        path_u = self.path_to_root(u)
        path_v = self.path_to_root(v)
        last = None
        limit = min(len(path_u), len(path_v))
        for i in range(1, limit + 1):
            if path_u[-i] == path_v[-i]:
                last = path_u[-i]
            else:
                break
        return last

    def distance(self, u, v):
        """树上两点距离：两次求祖先各得一步数，相加再减去公共部分。"""
        self._require(u)
        self._require(v)
        du = len(self.path_to_root(u)) - 1
        dv = len(self.path_to_root(v)) - 1
        w = self.lca(u, v)
        dw = len(self.path_to_root(w)) - 1
        return du + dv - 2 * dw

    def path(self, u, v):
        """u 到 v 的简单路径结点序列，含两端，按树上先后排列。"""
        self._require(u)
        self._require(v)
        w = self.lca(u, v)
        left = []
        cur = u
        while cur != w:
            left.append(cur)
            cur = self._parents[cur]
        left.append(w)
        right = []
        cur = v
        while cur != w:
            right.append(cur)
            cur = self._parents[cur]
        right.reverse()
        return left + right

    def path_sorted(self, u, v):
        """路径结点按编号升序排序后返回。"""
        return sorted(self.path(u, v))

    def on_path(self, x, u, v):
        """结点 x 是否落在 u 到 v 的简单路径上。"""
        self._require(x)
        self._require(u)
        self._require(v)
        return x in self.path(u, v)

    def paths_intersect(self, a1, a2, b1, b2):
        """a1 到 a2 的路径与 b1 到 b2 的路径是否有公共结点。"""
        return len(set(self.path(a1, a2)) & set(self.path(b1, b2))) > 0
