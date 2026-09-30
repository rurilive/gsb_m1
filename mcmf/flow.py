"""最小费用流的最简朴素实现。

用最直白的做法跑最大流：在残量网络里反复做广度优先搜索，
只要能找到一条从源点到汇点的路，就按这条路上最小的剩余容量整条推过去，
直到再也找不到增广路为止。整套流程完全不看单位费用，谁先被搜到就先用谁，
因此推出来的流量是最大的，但路径组合很随意，总费用通常不是最小的。

费用只是把每一条增广路推走的流量乘这条路上各边的单位费用再累加起来。
"""


class Erro(Exception):
    """本项目所有异常的基类。"""


class BadEdge(Erro):
    """边参数或节点非法时抛出。"""


class MinCostFlow:
    """朴素的最大流求解器，附带一个能对上的费用累加。

    add_edge(u, v, cap, cost)   加一条有向边，允许平行边
    edge_flows()                列出全部原始边的流量分解
    max_flow(s, t)              反复广度优先增广，返回最大流值
    flow_value()                当前已经推出去的流量
    flow_cost()                 当前流对应的累加费用
    nodes()                     出现过的节点
    """

    def __init__(self):
        self._to = []        # 每条半边的终点
        self._cap = []       # 每条半边的剩余容量
        self._cost = []      # 每条半边的单位费用
        self._used = []      # 每条半边上已经流过的量
        self._graph = {}     # 节点 -> 以它为起点的半边编号列表
        self._edges = []     # 原始边：(u, v, cap, cost, 正向半边编号)
        self._value = 0
        self._total = 0

    # -- 建图 ------------------------------------------------------------

    def add_edge(self, u, v, cap, cost):
        """加一条 u 到 v 的有向边，容量非负整数，费用可为负整数。"""
        if not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
            raise BadEdge("capacity must be a non-negative int")
        if not isinstance(cost, int) or isinstance(cost, bool):
            raise BadEdge("cost must be an int")
        if u not in self._graph:
            self._graph[u] = []
        if v not in self._graph:
            self._graph[v] = []
        i = len(self._to)
        self._to.append(v)
        self._cap.append(cap)
        self._cost.append(cost)
        self._used.append(0)
        self._to.append(u)
        self._cap.append(0)
        self._cost.append(-cost)
        self._used.append(0)
        self._graph[u].append(i)
        self._graph[v].append(i + 1)
        self._edges.append((u, v, cap, cost, i))

    def nodes(self):
        """返回出现过的节点，按首次出现的顺序。"""
        return list(self._graph)

    def edge_flows(self):
        """返回原始边的分解：每项是 (u, v, cap, cost, flow)。"""
        out = []
        for u, v, cap, cost, i in self._edges:
            out.append((u, v, cap, cost, self._used[i]))
        return out

    # -- 查询 ------------------------------------------------------------

    def flow_value(self):
        return self._value

    def flow_cost(self):
        return self._total

    # -- 朴素最大流 ------------------------------------------------------

    def max_flow(self, s, t):
        """反复广度优先找增广路，直到无路可增，返回最大流值。"""
        if s not in self._graph or t not in self._graph:
            raise BadEdge("unknown node")
        if s == t:
            return self._value
        while True:
            parent = self._bfs(s, t)
            if parent is None:
                break
            path = []
            v = t
            while v != s:
                eid = parent[v]
                path.append(eid)
                v = self._to[eid ^ 1]
            add = min(self._cap[eid] for eid in path)
            for eid in path:
                self._cap[eid] -= add
                self._cap[eid ^ 1] += add
                self._used[eid] += add
                self._used[eid ^ 1] -= add
            self._value += add
            self._total += add * sum(self._cost[eid] for eid in path)
        return self._value

    def _bfs(self, s, t):
        """从 s 出发广搜，返回到达各点时所用的半边编号，找不到 t 返回 None。"""
        parent = {}
        seen = {s}
        queue = [s]
        head = 0
        while head < len(queue):
            u = queue[head]
            head += 1
            if u == t:
                break
            for eid in self._graph[u]:
                v = self._to[eid]
                if self._cap[eid] > 0 and v not in seen:
                    seen.add(v)
                    parent[v] = eid
                    queue.append(v)
        if t not in seen:
            return None
        return parent
