"""graphx 的朴素实现（改造前基线）。

图用邻接表保存，节点只要求可哈希。连通、割点、割边按无向读边，
强连通分量按有向读边。本模块的全部判断都靠反复重扫整张图来回答：

- 连通分量：从每个未访问点重新扫一遍全图
- 割点：逐个把点删掉，再重扫一遍，看分量是否变多
- 割边：逐条把边删掉，再重扫一遍，看分量是否变多
- 强连通分量：以某点为核心反复删点，用两两互达把同分量筛出来
- 双路径互达边：逐条删边重扫，留下来的即为非割边

功能正确，规模一大就是逐点乘逐边再乘全图重扫，慢得明显。
"""


class GraphxError(Exception):
    """本库所有异常的基类。"""


class UnknownNodeError(GraphxError, KeyError):
    """引用了图里不存在的节点时抛出。"""


class EmptyGraphError(GraphxError, ValueError):
    """在空图上取强连通分量时抛出。"""


def _check_node(value):
    """节点校验：None 与不可哈希的对象一律拒。"""
    if value is None:
        raise UnknownNodeError("节点不能为 None")
    try:
        hash(value)
    except TypeError as exc:
        raise UnknownNodeError("节点必须可哈希") from exc
    return value


class Graph:
    """邻接表存的有向图，连通性一律按无向读。

    add_node / add_edge 建图；neighbors / out_degree 取结构；
    connected_components / is_connected / reachable 取连通性；
    split_vertices / bridges / bidirectional_edges 取割点与割边；
    scc 取强连通分量。sweep_count 记录全图重扫的次数。
    """

    def __init__(self):
        self._nodes = []
        self._index = {}
        self._edges = []
        self._out = {}
        self._sweeps = 0

    def add_node(self, value):
        _check_node(value)
        if value not in self._index:
            self._index[value] = len(self._nodes)
            self._nodes.append(value)
            self._out[value] = []
        return self

    def add_edge(self, u, v):
        _check_node(u)
        _check_node(v)
        self.add_node(u)
        self.add_node(v)
        self._out[u].append(len(self._edges))
        self._edges.append((u, v))
        return self

    def nodes(self):
        return list(self._nodes)

    def edges(self):
        return list(self._edges)

    def has_node(self, value):
        return value in self._index

    def node_count(self):
        return len(self._nodes)

    def edge_count(self):
        return len(self._edges)

    def neighbors(self, value):
        if value not in self._index:
            raise UnknownNodeError(value)
        return [self._edges[i][1] for i in self._out[value]]

    def out_degree(self, value):
        if value not in self._index:
            raise UnknownNodeError(value)
        return len(self._out[value])

    def sweep_count(self):
        return self._sweeps

    def reset_sweep_count(self):
        self._sweeps = 0
        return self

    def _adj(self, skip_node=None, skip_edge=None):
        """无向读：返回邻接表；可整体跳过某个点或某条边（按边下标）。"""
        adj = {value: [] for value in self._nodes}
        for idx, (u, v) in enumerate(self._edges):
            if skip_node is not None and (u == skip_node or v == skip_node):
                continue
            if skip_edge is not None and idx == skip_edge:
                continue
            adj[u].append(v)
            adj[v].append(u)
        return adj

    def _sweep(self, skip_node=None, skip_edge=None):
        """从每个未访问点重扫一遍全图，返回全部连通块，并记一次重扫。"""
        self._sweeps += 1
        adj = self._adj(skip_node, skip_edge)
        seen = set()
        comps = []
        for start in self._nodes:
            if start == skip_node or start in seen:
                continue
            stack = [start]
            seen.add(start)
            comp = []
            while stack:
                node = stack.pop()
                comp.append(node)
                for nxt in adj[node]:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            comps.append(comp)
        return comps

    def _directed_reach(self, src):
        """有向读：从 src 正向扫一遍，返回可达点集合，并记一次重扫。"""
        self._sweeps += 1
        adj = {value: [] for value in self._nodes}
        for u, v in self._edges:
            adj[u].append(v)
        seen = {src}
        stack = [src]
        while stack:
            node = stack.pop()
            for nxt in adj[node]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def connected_components(self):
        return [list(comp) for comp in self._sweep()]

    def component_count(self):
        return len(self._sweep())

    def is_connected(self):
        return len(self._sweep()) == 1

    def reachable(self, a, b):
        for value in (a, b):
            if value not in self._index:
                raise UnknownNodeError(value)
        if a == b:
            return True
        for comp in self._sweep():
            if a in comp:
                return b in comp
        return False

    def _mutually_reachable(self, a, b):
        """两点在有向口径下互相可达：各自正向重扫一遍。"""
        return b in self._directed_reach(a) and a in self._directed_reach(b)

    def split_vertices(self):
        """割点：逐个删点后重扫，分量比原来多即为割点。"""
        base = self.component_count()
        result = []
        for value in self._nodes:
            if len(self._sweep(skip_node=value)) > base:
                result.append(value)
        return result

    def bridges(self):
        """割边：逐条删边后重扫，分量比原来多即为割边（按边下标逐条）。"""
        base = self.component_count()
        result = []
        for idx in range(len(self._edges)):
            if len(self._sweep(skip_edge=idx)) > base:
                result.append(self._edges[idx])
        return result

    def bidirectional_edges(self):
        """双路径互达边：删掉后原图照旧连通，即非割边。"""
        cut = set(self.bridges())
        return [edge for edge in self._edges if edge not in cut]

    def _is_component_of(self, seed):
        """朴素判定：以 seed 为核心反复删点，只留与 seed 互相可达的点。"""
        keep = set()
        for value in self._nodes:
            if self._mutually_reachable(seed, value):
                keep.add(value)
        return [value for value in self._nodes if value in keep]

    def scc(self):
        """强连通分量：反复删点枚举，把同分量的点一簇一簇剥出来。"""
        if not self._nodes:
            raise EmptyGraphError("空图上没有强连通分量可取")
        remaining = set(self._nodes)
        comps = []
        for value in self._nodes:
            if value not in remaining:
                continue
            comp = self._is_component_of(value)
            comps.append(comp)
            remaining.difference_update(comp)
        return comps
