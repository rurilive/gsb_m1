"""有向无环图拓扑排序的朴素实现（改造前基线）。

用相邻结点表存放有向边，允许自环与平行边，边的输入下标就是它的编号。
求拓扑序的办法是最直白的反复全表线性扫描：每一轮从头到尾把全部结点扫一遍，
找出当前入度为零的点里编号最小的那个，取走它，再沿着它出去的每一条边把另一端
的剩余入度减一；取一个点就重扫一轮，每一轮还要把它出去的边重走一遍。有环时
总会在某一轮找不到零入度点，于是判定存在环。结果确定、也与编号挂钩，但轮数
与每轮重扫的结点数、边数双双上去，规模一多大就明显变慢。异常统一从 Erro 派生。
"""


class Erro(Exception):
    """本模块所有主动抛出异常的基类。"""


class InvalidGraphError(Erro):
    """建图参数非法：结点总数或边表不合规。"""


class NodeNotFoundError(Erro):
    """查询未登记或越界的结点编号。"""


class DirectedGraph:
    """有向图的朴素实现：相邻结点表加反复全表扫描求拓扑序。"""

    def __init__(self, node_count, edges):
        if not isinstance(node_count, int) or isinstance(node_count, bool):
            raise InvalidGraphError("结点总数必须是整数")
        if node_count <= 0:
            raise InvalidGraphError("结点总数必须为正")
        if not isinstance(edges, (list, tuple)):
            raise InvalidGraphError("边表必须是列表或元组")
        self._node_count = node_count
        self._edges = []
        self._adj = [[] for _ in range(node_count)]
        self._in_deg = [0] * node_count
        for item in edges:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise InvalidGraphError("每条边必须是两端点的二元组")
            u, v = item
            if not isinstance(u, int) or isinstance(u, bool):
                raise InvalidGraphError("边端点必须是整数")
            if not isinstance(v, int) or isinstance(v, bool):
                raise InvalidGraphError("边端点必须是整数")
            if u < 0 or u >= node_count or v < 0 or v >= node_count:
                raise InvalidGraphError("边端点越界")
            self._edges.append((u, v))
            self._adj[u].append(v)
            self._in_deg[v] += 1
        self._scan_visits = 0
        self._edge_visits = 0

    def node_count(self):
        return self._node_count

    def edge_count(self):
        return len(self._edges)

    def nodes(self):
        return list(range(self._node_count))

    def edges(self):
        return list(self._edges)

    def successors(self, u):
        self._require_node(u)
        return list(self._adj[u])

    def in_degrees(self):
        return list(self._in_deg)

    def _require_node(self, u):
        if not isinstance(u, int) or isinstance(u, bool) or u < 0 or u >= self._node_count:
            raise NodeNotFoundError("结点编号越界或未登记")
        return u

    def topological_order(self):
        """反复全表扫描求一个拓扑序；有环时返回 None。"""
        remaining = list(self._in_deg)
        alive = [True] * self._node_count
        order = []
        for _ in range(self._node_count):
            pick = -1
            for i in range(self._node_count):
                self._scan_visits += 1
                if alive[i] and remaining[i] == 0 and pick == -1:
                    pick = i
            if pick == -1:
                return None
            alive[pick] = False
            order.append(pick)
            for j in self._adj[pick]:
                self._edge_visits += 1
                remaining[j] -= 1
        return order

    def has_cycle(self):
        return self.topological_order() is None

    def reset_counters(self):
        self._scan_visits = 0
        self._edge_visits = 0

    def counters(self):
        return {"scan_visits": self._scan_visits, "edge_visits": self._edge_visits}
