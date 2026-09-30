"""PathTree: 朴素有根树的路径与子树统计（改造前基线）。

用父子边建一棵有根树，所有查询与更新都是逐节点遍历：

- depth(u)：顺着父指针一层层上爬，数到根为止
- lca(u, v)：两边各自逐层上爬，先把深度对齐，再一起爬到重合
- path_nodes(u, v)：把路径上的节点逐个收进列表
- path_sum(u, v)：沿路径把节点权值一个个加起来
- path_max(u, v)：沿路径逐个节点取最大值
- subtree_sum(u)：从 u 出发把子树里每个节点都访问一遍再加
- update(u, v, delta)：把路径上每个节点权值逐个加上增量
- add_subtree(u, delta)：把子树里每个节点权值逐个加上增量

节点用不重复的整数 id 标识。权值存在字典里，未显式设置的节点按 0 计。
每次操作都从头把点走一遍，链一长就退化成线性。
"""


class TreeError(Exception):
    """hldx 里所有可预期错误的基类。"""


class NodeNotFound(TreeError):
    """引用了不存在的节点 id。"""


class PathTree:
    """有根树：父子边重建，权值读写与朴素路径、子树统计。"""

    def __init__(self, root=None, edges=None):
        """建树。

        root 是根的 id；edges 是可选的 (parent, child) 二元组序列，
        边可以乱序给出，内部会按父子关系挂好。root 为 None 表示空树，
        此时不允许再给边。
        """
        self._root = root
        self._children = {}
        self._parent = {}
        self._weight = {}
        if root is not None:
            self._children[root] = []
            self._parent[root] = None
        if edges:
            if root is None:
                raise TreeError("空树不能挂边")
            for parent, child in edges:
                # 允许边乱序：父节点可能还没登记过子列表，先占位
                if parent not in self._children:
                    self._children[parent] = []
                    self._parent.setdefault(parent, None)
                if self._parent.get(child) is not None:
                    # 已经挂过父节点了，再挂就是重复边或环
                    raise TreeError("节点重复挂载: %r" % (child,))
                self._children.setdefault(child, [])
                self._parent[child] = parent
                if child not in self._children[parent]:
                    self._children[parent].append(child)
        # 子节点一律按 id 升序排好，边乱序给出也能得到同一棵确定的树
        for parent in self._children:
            self._children[parent].sort()
        self._check_reachable()

    # -- 内部校验 ---------------------------------------------------------

    def _check_reachable(self):
        """从根开始走一遍，确认每个登记过的节点都能从根到达。"""
        if self._root is None:
            return
        seen = set()
        stack = [self._root]
        while stack:
            u = stack.pop()
            if u in seen:
                raise TreeError("树里有环: %r" % (u,))
            seen.add(u)
            stack.extend(self._children.get(u, ()))
        registered = set(self._parent) | set(self._children)
        orphan = registered - seen
        if orphan:
            raise TreeError("存在从根不可达的节点: %r" % (sorted(orphan)[0],))

    def _require(self, u):
        if u not in self._parent:
            raise NodeNotFound("不存在的节点: %r" % (u,))
        return u

    # -- 只读视图 ---------------------------------------------------------

    @property
    def root(self):
        return self._root

    def nodes(self):
        """返回全部节点 id，顺序按建树时的父子登记顺序。"""
        return list(self._parent)

    def children(self, u):
        """返回 u 的子节点列表的副本。"""
        self._require(u)
        return list(self._children[u])

    def parent(self, u):
        """返回 u 的父节点 id，根返回 None。"""
        self._require(u)
        return self._parent[u]

    def weight(self, u):
        """返回 u 的权值，未设置过按 0 计。"""
        self._require(u)
        return self._weight.get(u, 0)

    def set_weight(self, u, value):
        """设置 u 的权值。"""
        self._require(u)
        self._weight[u] = value

    # -- 朴素操作 ---------------------------------------------------------

    def depth(self, u):
        """u 的深度，根算 0；顺着父指针一层层上爬数出来。"""
        self._require(u)
        d = 0
        cur = u
        while self._parent[cur] is not None:
            cur = self._parent[cur]
            d += 1
        return d

    def lca(self, u, v):
        """最近公共祖先：两边逐层上爬，先对齐深度再一起爬到重合。"""
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

    def path_nodes(self, u, v):
        """返回从 u 到 v 路径上的节点序列（含两端），供朴素统计共用。"""
        w = self.lca(u, v)
        left = []
        cur = u
        while cur != w:
            left.append(cur)
            cur = self._parent[cur]
        left.append(w)
        right = []
        cur = v
        while cur != w:
            right.append(cur)
            cur = self._parent[cur]
        right.reverse()
        return left + right

    def path_sum(self, u, v):
        """路径权值和：把路径上的节点权值一个个加起来。"""
        total = 0
        for node in self.path_nodes(u, v):
            total += self._weight.get(node, 0)
        return total

    def path_max(self, u, v):
        """路径权值最大值：沿路径逐个节点比一遍，空路径不存在。"""
        best = None
        for node in self.path_nodes(u, v):
            value = self._weight.get(node, 0)
            if best is None or value > best:
                best = value
        return best

    def _iter_subtree(self, u):
        """从 u 出发把子树每个节点都走一遍。"""
        stack = [u]
        while stack:
            cur = stack.pop()
            yield cur
            stack.extend(self._children[cur])

    def subtree_sum(self, u):
        """子树权值和：把子树里的节点逐个访问再加起来。"""
        self._require(u)
        total = 0
        for node in self._iter_subtree(u):
            total += self._weight.get(node, 0)
        return total

    def update(self, u, v, delta):
        """路径加：把路径上每个节点权值逐个加上增量，返回受影响的节点序列。"""
        touched = self.path_nodes(u, v)
        for node in touched:
            self._weight[node] = self._weight.get(node, 0) + delta
        return touched

    def add_subtree(self, u, delta):
        """子树加：把子树里每个节点权值逐个加上增量，返回受影响的节点序列。"""
        self._require(u)
        touched = list(self._iter_subtree(u))
        for node in touched:
            self._weight[node] = self._weight.get(node, 0) + delta
        return touched
