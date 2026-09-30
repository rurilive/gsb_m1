"""有向图的朴素实现：拓扑序、依赖调度与可达性计数全靠反复线性扫描。

做法是把产生式从头扫起：每一轮在整张图里从头找当前入度为零的点，
找到一个就取走一个，再沿着它出去的每一条边，把另一端点的剩余入度重算一次；
会合的判定靠反复扫描，一直扫到某一轮一个零入度点都找不到为止，那一轮里
还能被取走的点就是循环里的点。最早开始时间与关键路径也跟着每一轮重扫一遍。
规模一大，扫描轮数与每轮重扫的点数、边数双双上去，很慢，但结果正确。
"""


class TopoError(Exception):
    """本模块所有异常的基类。"""


class InvalidGraphError(TopoError):
    """图的规模或边的定义不合法。"""


class NodeNotFoundError(TopoError):
    """查询里出现了不在本图中的点编号。"""


class DirectedGraph(object):
    """一张有向图。

    点编号取 0 到 n-1，边以 (u, v) 的形式按输入先后给出，表示由 u 指向 v。
    允许自环与平行边，边的输入下标就是它的编号。构造时校验结构。
    """

    def __init__(self, n, edges):
        if not isinstance(n, int) or isinstance(n, bool):
            raise InvalidGraphError("点数必须是整数")
        if n < 1:
            raise InvalidGraphError("点数至少为一")
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
    # 计数：朴素实现把"扫一遍点"与"重扫一次边"都记下来。
    # ------------------------------------------------------------------
    def reset_counters(self):
        self._scan_visits = 0
        self._edge_visits = 0

    def counters(self):
        """返回 {'scan_visits': ..., 'edge_visits': ...}。"""
        return {
            "scan_visits": self._scan_visits,
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
        """全部点编号的升序列表。"""
        return list(range(self._n))

    def edges(self):
        """全部边，按输入先后给出 (u, v) 的列表。"""
        return list(self._edges)

    def _require_node(self, node):
        if not isinstance(node, int) or isinstance(node, bool):
            raise NodeNotFoundError("点 %r 不在图中" % (node,))
        if not 0 <= node < self._n:
            raise NodeNotFoundError("点 %r 不在图中" % (node,))

    # ------------------------------------------------------------------
    # 入度：每次都从头把整张图的边重数一遍。
    # ------------------------------------------------------------------
    def in_degrees(self):
        """每个点的当前入度，按点编号升序给出。"""
        deg = [0] * self._n
        for u, v in self._edges:
            self._edge_visits += 1
            deg[v] += 1
        return deg

    # ------------------------------------------------------------------
    # 拓扑序：反复在整张图里线性扫描找零入度点，每取走一个再逐边重算剩余入度。
    # ------------------------------------------------------------------
    def has_cycle(self):
        """图中是否存在有向环。"""
        remaining = self.in_degrees()
        removed = [False] * self._n
        emitted = 0
        while True:
            found = None
            for v in range(self._n):
                self._scan_visits += 1
                if not removed[v] and remaining[v] == 0:
                    found = v
                    break
            if found is None:
                return emitted < self._n
            removed[found] = True
            emitted += 1
            for u, v in self._edges:
                self._edge_visits += 1
                if u == found and not removed[v]:
                    remaining[v] -= 1

    def topological_order(self):
        """一个拓扑序，若图中有环则返回 None。可选点较多时取编号最小的那个。"""
        remaining = self.in_degrees()
        removed = [False] * self._n
        order = []
        while True:
            found = None
            for v in range(self._n):
                self._scan_visits += 1
                if removed[v]:
                    continue
                if remaining[v] == 0:
                    found = v
                    break
            if found is None:
                if len(order) == self._n:
                    return order
                return None
            removed[found] = True
            order.append(found)
            for u, v in self._edges:
                self._edge_visits += 1
                if u == found and not removed[v]:
                    remaining[v] -= 1

    def cycle_nodes(self):
        """一个具体的环上的点，按走环的先后给出；无环时返回空列表。"""
        remaining = self.in_degrees()
        removed = [False] * self._n
        while True:
            found = None
            for v in range(self._n):
                self._scan_visits += 1
                if not removed[v] and remaining[v] == 0:
                    found = v
                    break
            if found is None:
                rest = [v for v in range(self._n) if not removed[v]]
                if not rest:
                    return []
                return self._walk_cycle(rest)
            removed[found] = True
            for u, v in self._edges:
                self._edge_visits += 1
                if u == found and not removed[v]:
                    remaining[v] -= 1

    def _walk_cycle(self, rest):
        """在剩下的点里顺着没被摘掉的边走出一个环，给出环上的点。"""
        alive = set(rest)
        start = rest[0]
        path = []
        onpath = {}
        cur = start
        while cur not in onpath:
            onpath[cur] = len(path)
            path.append(cur)
            nxt = None
            for u, v in self._edges:
                self._edge_visits += 1
                if u == cur and v in alive:
                    nxt = v
                    break
            cur = nxt
        return path[onpath[cur]:]

    # ------------------------------------------------------------------
    # 最早开始时间与关键路径：每一轮都把整张图的边重扫一遍来推进工期。
    # ------------------------------------------------------------------
    def earliest_start(self, durations):
        """每个点的最早开始时间，按点编号升序给出；有环时返回 None。

        durations 可以是按点编号给出的列表，也可以是点编号到工期的映射，
        工期必须是非负整数。
        """
        dur = self._durations(durations)
        order = self.topological_order()
        if order is None:
            return None
        start = [0] * self._n
        for cur in order:
            for u, v in self._edges:
                self._edge_visits += 1
                if u == cur:
                    cand = start[cur] + dur[cur]
                    if cand > start[v]:
                        start[v] = cand
        return start

    def critical_path(self, durations):
        """关键路径上的点，按从源到汇的先后给出；有环时返回 None，无环时至少含一个点。"""
        dur = self._durations(durations)
        order = self.topological_order()
        if order is None:
            return None
        start = [0] * self._n
        for cur in order:
            for u, v in self._edges:
                self._edge_visits += 1
                if u == cur:
                    cand = start[cur] + dur[cur]
                    if cand > start[v]:
                        start[v] = cand
        finish = [start[v] + dur[v] for v in range(self._n)]
        end = None
        best = -1
        for v in order:
            if finish[v] > best:
                best = finish[v]
                end = v
        chain = [end]
        cur = end
        while True:
            pick = None
            for u, v in self._edges:
                self._edge_visits += 1
                if v != cur or finish[u] != start[cur]:
                    continue
                if pick is None or start[u] < start[pick]:
                    pick = u
            if pick is None:
                break
            chain.append(pick)
            cur = pick
        chain.reverse()
        return chain

    def _durations(self, durations):
        if isinstance(durations, dict):
            out = []
            for v in range(self._n):
                if v not in durations:
                    raise InvalidGraphError("点 %r 缺少工期" % (v,))
                out.append(self._one_duration(durations[v]))
            return out
        if isinstance(durations, (list, tuple)):
            if len(durations) != self._n:
                raise InvalidGraphError("工期表的长度必须等于点数")
            out = []
            for x in durations:
                out.append(self._one_duration(x))
            return out
        raise InvalidGraphError("工期必须是列表或按点编号的映射")

    def _one_duration(self, x):
        if not isinstance(x, int) or isinstance(x, bool):
            raise InvalidGraphError("工期必须是非负整数")
        if x < 0:
            raise InvalidGraphError("工期必须是非负整数")
        return x

    # ------------------------------------------------------------------
    # 可达性计数：每个点各做一次搜索，靠反复出队与重扫边来数。
    # ------------------------------------------------------------------
    def reachable_counts(self):
        """每个点能到达的点数，按点编号升序给出。"""
        out = []
        for v in range(self._n):
            out.append(self._reach_from(v))
        return out

    def reverse_reachable_counts(self):
        """每个点能被多少点到达，按点编号升序给出。"""
        radj = {}
        for v in range(self._n):
            radj[v] = []
        for u, v in self._edges:
            self._edge_visits += 1
            radj[v].append(u)
        out = []
        for v in range(self._n):
            out.append(self._search_count(radj, v))
        return out

    def _reach_from(self, src):
        adj = {}
        for v in range(self._n):
            adj[v] = []
        for u, v in self._edges:
            self._edge_visits += 1
            adj[u].append(v)
        return self._search_count(adj, src)

    def _search_count(self, adj, src):
        seen = set()
        queue = [src]
        seen.add(src)
        while queue:
            x = queue.pop(0)
            for y in adj[x]:
                self._edge_visits += 1
                if y not in seen:
                    seen.add(y)
                    queue.append(y)
        return len(seen) - 1
