"""domtree 的朴素支配关系实现：逐点删点判可达，纯标准库。

核心对象 DirectedGraph 只持一张有向图的邻接表。支配关系的求法是最直白
的那种：对一个起点，先算出它能到达的全部点；再对每个候选点 d 把 d 连同
它的出边从图里暂时拿掉，重算一次起点能到达的集合。若某个点 v 在删去 d
之后消失，就认定 d 支配 v。求全部支配点时，对起点可达的每个候选点都单
独删一次、单独从起点搜一遍，代价按点数乘边数甚至更高增长，规模一大就
顶不住，且结论算完即弃、从不留存复用。

对外能力：
  add_node(n) / add_edge(u, v)
  nodes() / edges() / neighbors(u) / has_node(u) / has_edge(u, v)
  reachable_from(src)                 起点可达集合，含起点自身
  reachable_without(src, removed)     拿掉 removed 之后的可达集合
  dominators(start)                   每个可达点的全部支配点，按升序
  immediate_dominators(start)         每个可达点的直接支配点，起点为 None
  dominator_edges(start)              支配树的边 (直接支配点, 点)，按字典序
  dominates(start, u, v)              u 是否支配 v，单次删点判可达
  children_of(start, u)               支配树上 u 的直接孩子，有序

按深度优先搜索编号、半支配点与并查集求交的线性做法、逐点删点这条独立对
照路径、边界与确定性见任务描述。
"""


class Erro(Exception):
    """本模块所有异常的基类，便于调用方一把兜住。"""


class IllegalArgument(Erro):
    """参数类型或取值非法。"""


class UnknownNode(Erro):
    """引用了未登记的节点。"""


class DirectedGraph(object):
    """朴素有向图，内部是一张节点到后继集合的邻接表。"""

    def __init__(self, nodes=None, edges=None):
        self._adj = {}
        for node in nodes or ():
            self.add_node(node)
        for u, v in edges or ():
            self.add_edge(u, v)

    # -- 建图 ------------------------------------------------------------

    def add_node(self, node):
        """登记一个节点，重复登记不改动已有出边。"""
        if node is None:
            raise IllegalArgument("节点不能为空")
        self._adj.setdefault(node, set())

    def add_edge(self, u, v):
        """加一条由 u 指向 v 的有向边，两端若未登记则补上。"""
        if u is None or v is None:
            raise IllegalArgument("边的两端不能为空")
        self.add_node(u)
        self.add_node(v)
        self._adj[u].add(v)

    # -- 结构查询 --------------------------------------------------------

    def nodes(self):
        return list(self._adj)

    def has_node(self, node):
        return node in self._adj

    def has_edge(self, u, v):
        return u in self._adj and v in self._adj[u]

    def edges(self):
        out = []
        for u in self._adj:
            for v in self._adj[u]:
                out.append((u, v))
        return sorted(out)

    def neighbors(self, u):
        """u 的直接后继，按升序。"""
        self._check_node(u)
        return sorted(self._adj[u])

    def _check_node(self, node):
        if node not in self._adj:
            raise UnknownNode(node)

    # -- 可达性（朴素广搜） ----------------------------------------------

    def reachable_from(self, src):
        """从 src 出发可达的节点集合，含 src 自身。"""
        self._check_node(src)
        return self._search(src, None)

    def reachable_without(self, src, removed):
        """拿掉 removed（连同它的出边）之后从 src 出发的可达集合。"""
        self._check_node(src)
        self._check_node(removed)
        if src == removed:
            return set()
        return self._search(src, removed)

    def _search(self, src, removed):
        """朴素广搜，用列表当栈，逐个弹出把未访问的后继推进去。"""
        seen = {src}
        stack = [src]
        while stack:
            u = stack.pop()
            for v in self._adj[u]:
                if v == removed or v in seen:
                    continue
                seen.add(v)
                stack.append(v)
        return seen

    # -- 支配关系（逐点删点判可达） --------------------------------------

    def dominators(self, start):
        """每个可达点的全部支配点，按升序给出。

        起点可达的每个候选点 d（起点自身除外）都单独删一次、单独搜一遍：
        删去 d 之后不可达的那些点，就把 d 记成它们的支配点。起点与点自身
        恒是支配点。起点不可达的点不参与支配关系，不出现在结果里。
        """
        self._check_node(start)
        reach = self.reachable_from(start)
        dom = {v: {start, v} for v in reach}
        for d in sorted(reach):
            if d == start:
                continue
            after = self._search(start, d)
            for v in reach:
                if v != d and v not in after:
                    dom[v].add(d)
        return {v: sorted(dom[v]) for v in sorted(reach)}

    def dominates(self, start, u, v):
        """判断 u 是否支配 v：把 u 拿掉，看 v 是否从 start 消失。

        v 不可达时返回 False；u 与 v 相同、或 u 就是起点时返回 True。
        """
        self._check_node(start)
        self._check_node(u)
        self._check_node(v)
        reach = self.reachable_from(start)
        if v not in reach:
            return False
        if u == v or u == start:
            return True
        return v not in self._search(start, u)

    def immediate_dominators(self, start):
        """每个可达点的直接支配点，起点为 None。

        直接支配点取严格支配点里最靠近该点的那个：它的支配点集合恰好等于
        该点去掉自己之后的支配点集合。
        """
        dom = self.dominators(start)
        result = {}
        for v in dom:
            if v == start:
                result[v] = None
                continue
            strict = set(dom[v]) - {v}
            chosen = None
            for d in dom[v]:
                if d == v:
                    continue
                if set(dom[d]) == strict:
                    chosen = d
                    break
            result[v] = chosen
        return result

    def dominator_edges(self, start):
        """支配树的边 (直接支配点, 点)，按字典序。起点不作为被支配端。"""
        idom = self.immediate_dominators(start)
        return sorted((idom[v], v) for v in idom if idom[v] is not None)

    def children_of(self, start, u):
        """支配树上 u 的直接孩子，按升序；u 不可达则返回空列表。"""
        self._check_node(u)
        idom = self.immediate_dominators(start)
        return sorted(v for v in idom if idom[v] == u)
