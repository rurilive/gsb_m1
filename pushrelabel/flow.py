"""pushrelabel 的现有能力：朴素增广路最大流与最小割。

朴素实现的做法很直白：

- 残量网络用一张邻接表记录，允许平行边各占一条；
- 找增广路时从源点出发做一次广度优先搜索，找到一条到汇点的残量路径
  就返回，不保证是最短的那条；
- 沿这条路径上各条残量的最小值逐条推流，推完再从源点重新找下一条；
- 最小割按汇点在残量网络里的可达性划分，源点侧是可达集合，汇点侧是补集。

这样的实现结果是对的，增广次数与流量大小同阶，容量一大就要走成千上万次，
边一多、规模一大就明显变慢。预流推进那种先沿源点出边饱和推流、再靠重标
记把余流推回去的做法还没有，本次改造要在这个基础上把它补出来。
"""

from collections import deque


class Erro(Exception):
    """网络流错误的基类。

    所有对外抛出的异常都继承它，调用方可以只捕获基类。
    """


class InvalidCapacityError(Erro):
    """容量不是非负整数时抛出。

    容量允许为 0，但不接受负数、布尔值与非整数。
    """


class NodeNotFoundError(Erro):
    """引用了网络中不存在的节点。"""


class SelfLoopError(Erro):
    """在同一个节点上连接了一条边。

    自环无法承载有效流，属于非法网络定义。
    """


class SourceSinkError(Erro):
    """源点或汇点取值不合法，或二者相同。"""


class NoPathError(Erro):
    """在残量网络上找不到任何增广路，却仍被要求继续推进。"""


class Edge(object):
    """一条有向边。

    属性：

    - src / dst：起点与终点
    - capacity：容量，非负整数
    - flow：当前流量
    - residual：剩余容量，等于容量减流量
    """

    __slots__ = ("src", "dst", "capacity", "flow")

    def __init__(self, src, dst, capacity, flow=0):
        self.src = src
        self.dst = dst
        self.capacity = capacity
        self.flow = flow

    @property
    def residual(self):
        """剩余容量。"""
        return self.capacity - self.flow

    def __repr__(self):
        return "Edge(%r, %r, capacity=%r, flow=%r)" % (
            self.src,
            self.dst,
            self.capacity,
            self.flow,
        )

    def __eq__(self, other):
        if not isinstance(other, Edge):
            return NotImplemented
        return (
            self.src == other.src
            and self.dst == other.dst
            and self.capacity == other.capacity
            and self.flow == other.flow
        )

    def __hash__(self):
        return hash((self.src, self.dst, self.capacity, self.flow))


class FlowResult(object):
    """一次最大流计算的结果。

    属性：

    - value：最大流的值
    - edges：按加入顺序给出的边对象副本，带着最终流量
    - augmentations：完成本次最大流所走的增广路次数
    """

    def __init__(self, value, edges, augmentations):
        self.value = value
        self.edges = edges
        self.augmentations = augmentations

    def __repr__(self):
        return "FlowResult(value=%r, augmentations=%r)" % (
            self.value,
            self.augmentations,
        )


class MinCutResult(object):
    """一次最小割计算的结果。

    属性：

    - value：最小割的容量，等于最大流的值
    - source_side：源点侧节点，按加入顺序给出
    - sink_side：汇点侧节点，按加入顺序给出
    - cut_edges：从源点侧跨到汇点侧的边，按加入顺序给出
    """

    def __init__(self, value, source_side, sink_side, cut_edges):
        self.value = value
        self.source_side = source_side
        self.sink_side = sink_side
        self.cut_edges = cut_edges

    def __repr__(self):
        return "MinCutResult(value=%r, source_side=%r, sink_side=%r)" % (
            self.value,
            self.source_side,
            self.sink_side,
        )


def _check_capacity(capacity):
    """容量必须是整数，且非负。"""
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise InvalidCapacityError("容量必须是整数: %r" % (capacity,))
    if capacity < 0:
        raise InvalidCapacityError("容量不能为负: %r" % (capacity,))
    return capacity


class FlowNetwork(object):
    """一张有向容量网络，允许平行边，禁止自环。

    节点可以是任意可哈希对象，按加入顺序维护。
    """

    def __init__(self, nodes=None):
        self._nodes = []
        self._node_set = set()
        self._edges = []
        if nodes is not None:
            for node in nodes:
                self.add_node(node)

    # -- 结构 -------------------------------------------------------------

    def add_node(self, node):
        """登记一个节点。"""
        if node not in self._node_set:
            self._node_set.add(node)
            self._nodes.append(node)
        return self

    def has_node(self, node):
        return node in self._node_set

    def nodes(self):
        """按加入顺序返回节点列表。"""
        return list(self._nodes)

    def add_edge(self, src, dst, capacity):
        """加一条有向边，返回这条边。

        平行边各占一条，互不影响；容量必须在加边处校验。
        """
        if not isinstance(src, str) or not isinstance(dst, str):
            raise NodeNotFoundError("节点名必须是字符串: %r -> %r" % (src, dst))
        if src == dst:
            raise SelfLoopError("不允许自环: %r" % (src,))
        _check_capacity(capacity)
        self.add_node(src)
        self.add_node(dst)
        edge = Edge(src, dst, capacity)
        self._edges.append(edge)
        return edge

    def edges(self):
        """按加入顺序返回全部边（内部对象，勿改动）。"""
        return list(self._edges)

    def node_count(self):
        return len(self._nodes)

    def edge_count(self):
        return len(self._edges)

    def neighbors(self, u):
        """u 的全部直接后继节点，按加入顺序、去重。"""
        if u not in self._node_set:
            raise NodeNotFoundError("未登记的节点: %r" % (u,))
        seen = []
        for edge in self._edges:
            if edge.src == u and edge.dst not in seen:
                seen.append(edge.dst)
        return seen

    # -- 残量网络 ---------------------------------------------------------

    def _out_edges(self, u):
        return [e for e in self._edges if e.src == u]

    def _residual_from(self, u):
        """从 u 出发的残量边：正向剩余量大于零的边，以及可回退的反向边。"""
        result = []
        for edge in self._edges:
            if edge.src == u and edge.residual > 0:
                result.append((edge, edge.dst, 1))
            if edge.dst == u and edge.flow > 0:
                result.append((edge, edge.src, -1))
        return result

    def _find_augmenting_path(self, source, sink):
        """从源点做一次广度搜索，返回一条到汇点的增广路。

        增广路是一串 (边, 方向) 对，方向为 1 表示沿边正向推流，
        为 -1 表示沿边回退；找不到时返回空列表。
        """
        seen = set([source])
        queue = deque([(source, [])])
        while queue:
            node, path = queue.popleft()
            if node == sink:
                return path
            for edge, nxt, sign in self._residual_from(node):
                if nxt in seen:
                    continue
                seen.add(nxt)
                queue.append((nxt, path + [(edge, sign)]))
        return []

    def augment(self, source, sink):
        """朴素推进一次增广：找一条增广路，沿路推流。

        返回这次推流推了多少，找不到增广路返回 0。
        """
        path = self._find_augmenting_path(source, sink)
        if not path:
            return 0
        bottleneck = None
        for edge, sign in path:
            amount = edge.residual if sign == 1 else edge.flow
            if bottleneck is None or amount < bottleneck:
                bottleneck = amount
        for edge, sign in path:
            if sign == 1:
                edge.flow += bottleneck
            else:
                edge.flow -= bottleneck
        return bottleneck

    def reachable_from(self, source):
        """残量网络上从源点出发可达的节点，按加入顺序给出。"""
        if source not in self._node_set:
            raise NodeNotFoundError("未登记的节点: %r" % (source,))
        seen = set([source])
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for _, nxt, _ in self._residual_from(node):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return [n for n in self._nodes if n in seen]

    def value(self, source, sink):
        """当前网络的流量值：从源点流出的净流量之和。"""
        return sum(e.flow for e in self._out_edges(source))

    def copy(self):
        """复制一张结构相同、流量清零的网络。"""
        clone = FlowNetwork()
        for node in self._nodes:
            clone.add_node(node)
        for edge in self._edges:
            clone.add_edge(edge.src, edge.dst, edge.capacity)
        return clone

    def __repr__(self):
        return "FlowNetwork(nodes=%d, edges=%d)" % (
            len(self._nodes),
            len(self._edges),
        )


def _validate_terminals(network, source, sink):
    if source not in network._node_set:
        raise NodeNotFoundError("源点未登记: %r" % (source,))
    if sink not in network._node_set:
        raise NodeNotFoundError("汇点未登记: %r" % (sink,))
    if source == sink:
        raise SourceSinkError("源点与汇点不能相同: %r" % (source,))


def max_flow(network, source, sink):
    """用朴素增广路方法求最大流。

    反复在残量网络上找一条增广路并沿路推流，直到找不到为止。
    """
    _validate_terminals(network, source, sink)
    work = network.copy()
    augmentations = 0
    while True:
        pushed = work.augment(source, sink)
        if pushed == 0:
            break
        augmentations += 1
    result_edges = []
    for original, computed in zip(network._edges, work._edges):
        result_edges.append(
            Edge(original.src, original.dst, computed.capacity, computed.flow)
        )
    return FlowResult(work.value(source, sink), result_edges, augmentations)


def min_cut(network, source, sink):
    """用朴素方法求最小割。

    先跑一遍最大流把残量网络定下来，再按源点在残量网络上的可达性划分：
    可达的是源点侧，剩下的是汇点侧，割边从源点侧跨到汇点侧。
    """
    _validate_terminals(network, source, sink)
    flow_result = max_flow(network, source, sink)
    work = network.copy()
    for computed, final in zip(work._edges, flow_result.edges):
        computed.flow = final.flow
    reach = work.reachable_from(source)
    reach_set = set(reach)
    cut_edges = [
        edge
        for edge in flow_result.edges
        if edge.src in reach_set and edge.dst not in reach_set
    ]
    value = sum(edge.capacity for edge in cut_edges)
    source_side = [n for n in network._nodes if n in reach_set]
    sink_side = [n for n in network._nodes if n not in reach_set]
    return MinCutResult(value, source_side, sink_side, cut_edges)
