"""spannex.graph: 生成树的朴素基线实现。

现状只回答一件事：一张无向图是不是连通的。做法是最朴素的反复扫描：
从一组已访问节点出发，每一轮把全部节点从头到尾扫一遍，凡是与已访问集合
相邻的节点就并进来；一轮扫完若没有新节点进来就收工。没有排序，没有并查集，
也没有任何最小生成树的构造。
"""


class SpannError(Exception):
    """生成树工具包的基类异常。"""


class UnknownNode(SpannError):
    """引用了未登记的节点。"""


class BruteSpan:
    """无向图的朴素连通判断。

    节点用名字标识，边不带权，只记录两点之间有没有边。内部不维护
    邻接表，每次判断都重新对全量节点反复扫描，节点一多就明显变慢。
    """

    def __init__(self, nodes=None):
        self._nodes = []
        self._edges = []
        if nodes is not None:
            for name in nodes:
                self.add_node(name)

    def add_node(self, name):
        """登记一个节点，重复登记不改动已有结构。"""
        if not isinstance(name, str) or not name:
            raise SpannError("节点名必须是非空字符串")
        if name not in self._nodes:
            self._nodes.append(name)

    def add_edge(self, a, b):
        """加一条无向边，端点必须已登记。"""
        for name in (a, b):
            if name not in self._nodes:
                raise UnknownNode(name)
        self._edges.append((a, b))

    def nodes(self):
        """返回节点名列表，按登记顺序。"""
        return list(self._nodes)

    def edges(self):
        """返回边列表，按加入顺序，每条边形如 (a, b)。"""
        return list(self._edges)

    def has_edge(self, a, b):
        """两点之间是否有边，无向。"""
        for x, y in self._edges:
            if (x == a and y == b) or (x == b and y == a):
                return True
        return False

    def _neighbors(self, name):
        """朴素求邻居：把每条边摸一遍。"""
        result = []
        for x, y in self._edges:
            if x == name and y not in result:
                result.append(y)
            elif y == name and x not in result:
                result.append(x)
        return result

    def reached_from(self, start):
        """从起点出发，反复扫描全量节点求可达集合，结果按登记顺序。"""
        if start not in self._nodes:
            raise UnknownNode(start)
        seen = [start]
        changed = True
        while changed:
            changed = False
            for name in self._nodes:
                if name in seen:
                    continue
                for other in seen:
                    if self.has_edge(name, other):
                        seen.append(name)
                        changed = True
                        break
        return [name for name in self._nodes if name in seen]

    def connected(self, a, b):
        """两点是否连通，自身与自身视为连通。"""
        return b in self.reached_from(a)

    def is_connected(self):
        """整张图是否连通：空图与单点图视为连通。"""
        if not self._nodes:
            return True
        return len(self.reached_from(self._nodes[0])) == len(self._nodes)
