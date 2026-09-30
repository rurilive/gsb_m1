"""lct 的现有实现：用最直白的邻接表加深度优先搜索维护一片森林。

当前只有一套最朴素的做法，每一种查询都从头把相关部分重新遍历一遍：

    连通性 connected(u, v)      从 u 起深搜，看能否走到 v
    加边 link(u, v)             记两个方向各一条邻接边，顺带查一次连通性
    删边 cut(u, v)              在两边邻接表里各扫一遍找对端再删
    路径点权和 path_sum(u,v)    从 u 起深搜，记下到 v 的整条路径再逐个累加
    路径点权最小 path_min(u,v)  拿到整条路径的顶点后逐个比较
    路径点权最大 path_max(u,v)  拿到整条路径的顶点后逐个比较
    点权设置 set_value(u, x)    直接写进字典

这些做法结果都对，但每次查询都要把整片连通的森林重新走一遍，操作一多、
规模一大就退化成线性甚至更高。这里没有树、没有分层结构，也压不下重复
查询的代价。
"""


class Erro(Exception):
    """本工具所有异常的基类。

    调用方可以只捕获 Erro 就把本工具抛出的所有错误一网打尽，
    不必逐个记住具体异常类型的名字。
    """


class UnknownNodeErro(Erro):
    """访问了尚未登记的点时抛出。"""


class LinkErro(Erro):
    """加边请求非法时抛出。"""


class CutErro(Erro):
    """删边请求非法时抛出。"""


class ArgErro(Erro):
    """参数类型或取值非法时抛出。"""


class Forest:
    """一片带点权的森林，用邻接表直接承载。

    点用整数标识，取值范围从零到 n 减一，构造时按这个范围一次性登记。
    森林里每一条边都是双向可达的连通关系。点权是可比较的整数，求最小值
    与最大值时按整数大小比较。所有操作都在原位生效。
    """

    def __init__(self, n):
        self._check_node_id(n, "n")
        if n < 0:
            raise ArgErro("n must not be negative")
        self._n = n
        self._value = {}
        self._adj = {}
        for node in range(n):
            self._value[node] = 0
            self._adj[node] = []
        self.edge_count = 0

    def size(self):
        """点的个数。"""
        return self._n

    def set_value(self, u, x):
        """把点 u 的点权设成 x。"""
        self._check_node(u)
        self._check_int(x, "x")
        self._value[u] = x

    def get_value(self, u):
        """取点 u 的点权。"""
        self._check_node(u)
        return self._value[u]

    def has_edge(self, u, v):
        """判断 u 与 v 之间是否存在一条边。"""
        self._check_node(u)
        self._check_node(v)
        for other in self._adj[u]:
            if other == v:
                return True
        return False

    def connected(self, u, v):
        """判断点 u 与点 v 是否在同一棵连通树里，从 u 起深搜整棵树。"""
        self._check_node(u)
        self._check_node(v)
        seen = self._reachable(u)
        return v in seen

    def link(self, u, v):
        """在 u 与 v 之间连一条边；两点已连通或本来就有边时拒绝。"""
        self._check_node(u)
        self._check_node(v)
        if u == v:
            raise LinkErro("self loop is not allowed")
        if self.connected(u, v):
            raise LinkErro("linking would create a cycle")
        self._adj[u].append(v)
        self._adj[v].append(u)
        self.edge_count = self.edge_count + 1

    def cut(self, u, v):
        """断开 u 与 v 之间的边；这条边不存在时拒绝。"""
        self._check_node(u)
        self._check_node(v)
        if u == v:
            raise CutErro("self loop is not an edge")
        removed = False
        i = 0
        while i < len(self._adj[u]):
            if self._adj[u][i] == v:
                self._adj[u].pop(i)
                removed = True
                break
            i = i + 1
        if not removed:
            raise CutErro("edge does not exist")
        i = 0
        while i < len(self._adj[v]):
            if self._adj[v][i] == u:
                self._adj[v].pop(i)
                break
            i = i + 1
        self.edge_count = self.edge_count - 1

    def path(self, u, v):
        """返回 u 到 v 路径上的顶点序列；两点不连通时返回空列表。

        从 u 起深搜，一旦摸到 v 就沿父指针回溯出整条路径。
        """
        self._check_node(u)
        self._check_node(v)
        if u == v:
            return [u]
        parent = {u: None}
        stack = [u]
        found = False
        while stack:
            current = stack.pop()
            if current == v:
                found = True
                break
            for neighbour in self._adj[current]:
                if neighbour not in parent:
                    parent[neighbour] = current
                    stack.append(neighbour)
        if not found:
            return []
        result = []
        node = v
        while node is not None:
            result.append(node)
            node = parent[node]
        reverse = []
        i = len(result) - 1
        while i >= 0:
            reverse.append(result[i])
            i = i - 1
        return reverse

    def path_sum(self, u, v):
        """求 u 到 v 路径上所有点权之和；两点不连通时抛 LinkErro。"""
        nodes = self._reachable_path(u, v)
        total = 0
        for node in nodes:
            total = total + self._value[node]
        return total

    def path_min(self, u, v):
        """求 u 到 v 路径上点权的最小值；两点不连通时抛 LinkErro。"""
        nodes = self._reachable_path(u, v)
        best = self._value[nodes[0]]
        i = 1
        while i < len(nodes):
            if self._value[nodes[i]] < best:
                best = self._value[nodes[i]]
            i = i + 1
        return best

    def path_max(self, u, v):
        """求 u 到 v 路径上点权的最大值；两点不连通时抛 LinkErro。"""
        nodes = self._reachable_path(u, v)
        best = self._value[nodes[0]]
        i = 1
        while i < len(nodes):
            if self._value[nodes[i]] > best:
                best = self._value[nodes[i]]
            i = i + 1
        return best

    def _reachable_path(self, u, v):
        self._check_node(u)
        self._check_node(v)
        nodes = self.path(u, v)
        if not nodes:
            raise LinkErro("nodes are not connected")
        return nodes

    def _reachable(self, source):
        seen = {source: True}
        stack = [source]
        while stack:
            current = stack.pop()
            for neighbour in self._adj[current]:
                if neighbour not in seen:
                    seen[neighbour] = True
                    stack.append(neighbour)
        return seen

    def _check_node(self, u):
        self._check_node_id(u, "node")
        if u < 0 or u >= self._n:
            raise UnknownNodeErro("node id out of range")

    def _check_node_id(self, value, name):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ArgErro(name + " must be int")

    def _check_int(self, value, name):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ArgErro(name + " must be int")
