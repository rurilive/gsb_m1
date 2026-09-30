"""无向图的朴素实现：割边、割点与双连通分量全靠反复重判连通性。

每条边或每个点都尝试删掉一次，再用深度或广度搜索重判全图是否变松散，
据此判定割边与割点；双连通分量则靠把割边摘掉之后再看连通性变化来分。
规模一大重判次数与每次重扫的边数双双上去，很慢，但结果正确。
"""


class GraphError(Exception):
    """本模块所有异常的基类。"""


class InvalidGraphError(GraphError):
    """图的规模或边的定义不合法。"""


class NodeNotFoundError(GraphError):
    """查询里出现了不在本图中的结点编号。"""


class UndirectedGraph(object):
    """一张无向图。

    结点编号取 0 到 n-1，边以 (u, v) 的形式按输入先后给出，
    允许重边与自环，边在输入里的下标就是它的编号。构造时校验结构。
    """

    def __init__(self, n, edges):
        if not isinstance(n, int) or isinstance(n, bool):
            raise InvalidGraphError("结点数必须是整数")
        if n < 1:
            raise InvalidGraphError("结点数至少为一")
        if not isinstance(edges, (list, tuple)):
            raise InvalidGraphError("边集必须是列表或元组")
        self._n = n
        self._edges = []
        for e in edges:
            if not isinstance(e, (list, tuple)) or len(e) != 2:
                raise InvalidGraphError("每条边必须是两个端点的二元组")
            u, v = e[0], e[1]
            if not isinstance(u, int) or isinstance(u, bool):
                raise InvalidGraphError("端点编号必须是整数")
            if not isinstance(v, int) or isinstance(v, bool):
                raise InvalidGraphError("端点编号必须是整数")
            if not (0 <= u < n) or not (0 <= v < n):
                raise InvalidGraphError("端点 %r 或 %r 越界" % (u, v))
            self._edges.append((u, v))
        self.reset_counters()

    # ------------------------------------------------------------------
    # 计数：朴素实现把"重判一次连通性"与"重扫一条边"都记下来。
    # ------------------------------------------------------------------
    def reset_counters(self):
        self._connectivity_checks = 0
        self._edge_visits = 0

    def counters(self):
        """返回 {'connectivity_checks': ..., 'edge_visits': ...}。"""
        return {
            "connectivity_checks": self._connectivity_checks,
            "edge_visits": self._edge_visits,
        }

    # ------------------------------------------------------------------
    # 基本访问
    # ------------------------------------------------------------------
    def node_count(self):
        return self._n

    def edge_count(self):
        return len(self._edges)

    def nodes(self):
        """全部结点编号的升序列表。"""
        return list(range(self._n))

    def edges(self):
        """全部边，按输入先后给出 (u, v) 的列表。"""
        return list(self._edges)

    def _require_edge(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise InvalidGraphError("边的编号必须是整数")
        if not 0 <= index < len(self._edges):
            raise InvalidGraphError("边编号 %r 越界" % (index,))

    def _require_node(self, node):
        if not isinstance(node, int) or isinstance(node, bool):
            raise NodeNotFoundError("结点 %r 不在图中" % (node,))
        if not 0 <= node < self._n:
            raise NodeNotFoundError("结点 %r 不在图中" % (node,))

    # ------------------------------------------------------------------
    # 连通性：每次都现搭一张邻接表，再整图重扫一遍。
    # ------------------------------------------------------------------
    def _build_adj(self, skip_edge, skip_node):
        adj = {}
        for v in range(self._n):
            adj[v] = []
        for idx, (u, v) in enumerate(self._edges):
            if idx == skip_edge:
                continue
            if u == skip_node or v == skip_node:
                continue
            adj[u].append((v, idx))
            adj[v].append((u, idx))
        return adj

    def _reachable(self, start, adj):
        seen = set()
        stack = [start]
        seen.add(start)
        while stack:
            x = stack.pop()
            for y, _idx in adj[x]:
                self._edge_visits += 1
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        return seen

    def _label(self, skip_edge=None, skip_node=None):
        """给每个保留结点贴一个分量标号，返回 (标号表, 分量个数)。"""
        adj = self._build_adj(skip_edge, skip_node)
        label = {}
        count = 0
        for start in range(self._n):
            if start == skip_node or start in label:
                continue
            comp = self._reachable(start, adj)
            for x in comp:
                label[x] = count
            count += 1
        return label, count

    def _component_count(self, skip_edge=None, skip_node=None):
        _label, count = self._label(skip_edge, skip_node)
        self._connectivity_checks += 1
        return count

    def is_connected(self):
        """整张图是否只有一个连通分量。"""
        return self._component_count() <= 1

    def connected(self, u, v):
        """两点是否在同一连通分量里。"""
        self._require_node(u)
        self._require_node(v)
        label, _count = self._label()
        return label[u] == label[v]

    def _has_path(self, u, v, skip_edge=None, skip_node=None):
        label, _count = self._label(skip_edge, skip_node)
        if u not in label or v not in label:
            return False
        return label[u] == label[v]

    # ------------------------------------------------------------------
    # 割边与割点：逐一删掉再数连通分量，分量变多就是割。
    # ------------------------------------------------------------------
    def bridges(self):
        """割边编号列表，按边的输入先后给出。"""
        base = self._component_count()
        out = []
        for idx in range(len(self._edges)):
            if self._component_count(skip_edge=idx) > base:
                out.append(idx)
        return out

    def articulation_points(self):
        """割点编号列表，按编号升序给出。"""
        base = self._component_count()
        out = []
        for v in range(self._n):
            if self._component_count(skip_node=v) > base:
                out.append(v)
        return out

    # ------------------------------------------------------------------
    # 双连通分量：把割边摘掉之后，再看连通性变化来分组。
    # ------------------------------------------------------------------
    def edge_components(self):
        """边双连通分量：每组是一批边编号，组内边编号升序，组间按首个编号升序。"""
        bridge_set = set(self.bridges())
        keep = [idx for idx in range(len(self._edges)) if idx not in bridge_set]
        adj = {}
        for v in range(self._n):
            adj[v] = []
        for idx in keep:
            u, v = self._edges[idx]
            adj[u].append(v)
            adj[v].append(u)
        label = {}
        gid = 0
        for start in range(self._n):
            if start in label:
                continue
            stack = [start]
            label[start] = gid
            while stack:
                x = stack.pop()
                for y in adj[x]:
                    if y not in label:
                        label[y] = gid
                        stack.append(y)
            gid += 1
        groups = {}
        for idx in keep:
            u, _v = self._edges[idx]
            groups.setdefault(label[u], []).append(idx)
        out = [sorted(members) for members in groups.values()]
        for idx in sorted(bridge_set):
            out.append([idx])
        out.sort(key=lambda members: members[0])
        return out

    def vertex_components(self):
        """点分量：摘掉全部割边后，把结点按连通性分组，组内升序，组间按首元素升序。"""
        bridge_set = set(self.bridges())
        adj = {}
        for v in range(self._n):
            adj[v] = []
        for idx, (u, v) in enumerate(self._edges):
            if idx in bridge_set:
                continue
            adj[u].append(v)
            adj[v].append(u)
        label = {}
        groups = []
        for start in range(self._n):
            if start in label:
                continue
            comp = []
            stack = [start]
            label[start] = len(groups)
            while stack:
                x = stack.pop()
                comp.append(x)
                for y in adj[x]:
                    if y not in label:
                        label[y] = len(groups)
                        stack.append(y)
            groups.append(sorted(comp))
        groups.sort(key=lambda members: members[0])
        return groups

    def bridge_tree(self):
        """把点分量缩成一个点，割边变成缩点之间的边。

        返回 {'components': 点分量列表, 'bridges': [(左分量号, 右分量号, 边编号), ...]}，
        缩点用它在 components 里的下标表示，割边按输入先后排列。
        """
        comps = self.vertex_components()
        comp_of = {}
        for i, members in enumerate(comps):
            for v in members:
                comp_of[v] = i
        links = []
        for idx in self.bridges():
            u, v = self._edges[idx]
            links.append((comp_of[u], comp_of[v], idx))
        return {"components": comps, "bridges": links}

    # ------------------------------------------------------------------
    # 必经判定：某条边或某个点是否在两点之间的每条路上。
    # ------------------------------------------------------------------
    def must_pass_edge(self, u, v, index):
        """u 到 v 的每条简单路是否都经过编号 index 的边。"""
        self._require_node(u)
        self._require_node(v)
        self._require_edge(index)
        return not self._has_path(u, v, skip_edge=index)

    def must_pass_node(self, u, v, node):
        """u 到 v 的每条简单路是否都经过结点 node。"""
        self._require_node(u)
        self._require_node(v)
        self._require_node(node)
        return not self._has_path(u, v, skip_node=node)
