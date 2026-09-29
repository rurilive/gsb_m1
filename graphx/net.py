"""graphx.net: 朴素有向图（仅遍历，无流量概念）。

现有实现只做一件事：用邻接表维护一张朴素有向图，并在图上做深度优先
与广度优先遍历。它只回答"能不能到""按什么顺序到"这类问题，完全没有
流量、容量、割或匹配的概念，任何与容量有关的问题这里都答不了。
"""


class GraphError(Exception):
    """graphx 的业务异常基类。"""


class UnknownNode(GraphError):
    """引用了未登记的节点。"""


class FlatNet:
    """朴素有向图：邻接表建图 + 遍历。

    邻接表按添加顺序保存每条出边，出边为三元组（邻点、容量、序号），
    容量只被原样记录，不参与任何计算。可达性与广度顺序都只看出边是否存在。
    """

    def __init__(self):
        self._adj = {}
        self._order = []
        self._edges = []

    # --- 建图 ---

    def add_node(self, name):
        if not isinstance(name, str) or not name:
            raise GraphError("节点名必须是非空字符串")
        if name in self._adj:
            return
        self._adj[name] = []
        self._order.append(name)

    def add_edge(self, u, v, cap=0):
        self.add_node(u)
        self.add_node(v)
        if not isinstance(cap, (int, float)) or isinstance(cap, bool):
            raise GraphError("容量必须是数值")
        seq = len(self._edges)
        self._adj[u].append((v, cap, seq))
        self._edges.append((u, v, cap))

    # --- 统计 ---

    def node_count(self):
        return len(self._order)

    def edge_count(self):
        return len(self._edges)

    def nodes(self):
        return list(self._order)

    def has_node(self, name):
        return name in self._adj

    def edges(self):
        return list(self._edges)

    def neighbors(self, u):
        self._require(u)
        return [(v, cap) for (v, cap, _seq) in self._adj[u]]

    def out_degree(self, u):
        self._require(u)
        return len(self._adj[u])

    # --- 遍历 ---

    def reachable(self, s, t):
        self._require(s)
        self._require(t)
        seen = {s}
        stack = [s]
        while stack:
            node = stack.pop()
            if node == t:
                return True
            for (v, _cap, _seq) in self._adj[node]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return t in seen

    def bfs_order(self, s):
        self._require(s)
        seen = {s}
        order = []
        queue = [s]
        head = 0
        while head < len(queue):
            node = queue[head]
            head += 1
            order.append(node)
            for (v, _cap, _seq) in self._adj[node]:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        return order

    def _require(self, name):
        if name not in self._adj:
            raise UnknownNode(name)
