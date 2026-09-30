"""treecover 的朴素基线实现（改造前）。

一棵无向简单树，用整数编号，邻接表逐条累积。这一层里所有覆盖类问题都只靠
枚举顶点子集、逐个检查是否满足要求来求解，二的节点数次方的量级，结果正确但
规模一大就崩。所有对外函数都是模块级函数，不保存任何跨调用的状态。
"""


class CoverError(Exception):
    """treecover 的错误基类，覆盖类问题遇到非法输入时统一抛出它或它的子类。"""


class NotATreeError(CoverError):
    """输入不是一棵树（顶点集为空，或边数与连通性不成树）时抛出。"""


class EmptyTreeError(NotATreeError):
    """树里一个顶点都没有时抛出，是 NotATreeError 的更具体一种。"""


def _sorted_vertices(adjacency):
    """把邻接表里的顶点收集成升序列表。"""
    return sorted(adjacency.keys())


def _is_tree(adjacency):
    """检查无向图是否为一棵树：边数等于顶点数减一且连通。"""
    vertices = _sorted_vertices(adjacency)
    if not vertices:
        return False
    edges = 0
    for node in vertices:
        edges += len(adjacency[node])
    edges //= 2
    if edges != len(vertices) - 1:
        return False
    seen = {vertices[0]}
    stack = [vertices[0]]
    while stack:
        node = stack.pop()
        for other in adjacency[node]:
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return len(seen) == len(vertices)


class Tree:
    """无向简单树，顶点用整数编号，边用邻接表逐条累积。"""

    def __init__(self, root=None):
        self.root = root
        self._adjacency = {}
        self._weights = {}
        if root is not None:
            self._touch(root)

    def _touch(self, node):
        if node not in self._adjacency:
            self._adjacency[node] = []

    def add_edge(self, u, v, weight=1):
        """在 u 与 v 之间加一条无向边，权重可正可负可零。"""
        if u == v:
            raise CoverError("不允许自环")
        self._touch(u)
        self._touch(v)
        self._adjacency[u].append(v)
        self._adjacency[v].append(u)
        self._weights[(u, v)] = weight
        self._weights[(v, u)] = weight

    def add_vertex(self, node):
        """单独登记一个孤立顶点（用于构造单节点这类退化输入）。"""
        self._touch(node)

    def vertices(self):
        """全部顶点，升序。"""
        return _sorted_vertices(self._adjacency)

    def neighbors(self, v):
        """v 的邻接点，升序。"""
        if v not in self._adjacency:
            raise CoverError("顶点不存在：%r" % (v,))
        return sorted(self._adjacency[v])

    def edge_weight(self, u, v):
        """取 u 与 v 之间那条边的权重。"""
        if (u, v) not in self._weights:
            raise CoverError("边不存在：%r-%r" % (u, v))
        return self._weights[(u, v)]

    def edges(self):
        """全部无向边，统一按 (较小端点, 较大端点) 给出并升序排列。"""
        result = []
        for u in self._adjacency:
            for v in self._adjacency[u]:
                if u < v:
                    result.append((u, v))
        result.sort()
        return result

    def vertex_weights(self, weight_map=None):
        """取每个顶点的权：给了映射就按映射，缺省全部为 1。"""
        result = {}
        for node in self._adjacency:
            if weight_map is None:
                result[node] = 1
            else:
                result[node] = weight_map.get(node, 1)
        return result


def _weight_map_of(tree, weight_map):
    """把可选的点权映射规整成每个顶点都有值的字典，缺省全 1。"""
    if weight_map is None:
        return {node: 1 for node in tree.vertices()}
    return {node: weight_map.get(node, 1) for node in tree.vertices()}


def _check_tree(tree):
    """确认输入是一棵树，否则按统一口径抛错。"""
    vertices = tree.vertices()
    if not vertices:
        raise EmptyTreeError("空树没有覆盖类问题可解")
    if not _is_tree(tree._adjacency):
        raise NotATreeError("输入不是一棵树")


def enumerate_subsets(nodes):
    """按字典序枚举顶点集的所有子集，每个子集用升序元组给出。

    这是全部覆盖类问题的共同底色：按二进制计数从 0 数到 2 的 n 次方减一，
    逐位取出被选中的顶点，二的节点数次方的量级。
    """
    ordered = sorted(nodes)
    total = 1 << len(ordered)
    for mask in range(total):
        chosen = []
        for i in range(len(ordered)):
            if mask & (1 << i):
                chosen.append(ordered[i])
        yield tuple(chosen)


def is_dominating_set(tree, subset):
    """判断 subset 是否为支配集：每个顶点要么在集合里，要么与集合里的点相邻。"""
    chosen = set(subset)
    for v in tree.vertices():
        if v in chosen:
            continue
        hit = False
        for neighbor in tree.neighbors(v):
            if neighbor in chosen:
                hit = True
                break
        if not hit:
            return False
    return True


def is_vertex_cover(tree, subset):
    """判断 subset 是否为点覆盖：每一条边至少有一个端点在集合里。"""
    chosen = set(subset)
    for u, v in tree.edges():
        if u not in chosen and v not in chosen:
            return False
    return True


def is_independent_set(tree, subset):
    """判断 subset 是否为独立集：集合里没有任何一条边两端都在集合中。"""
    chosen = set(subset)
    for node in chosen:
        for neighbor in tree.neighbors(node):
            if neighbor in chosen:
                return False
    return True


def min_dominating_set(tree):
    """最小支配集：枚举全部子集，按大小取最小，并列时按顶点集合字典序取最小。

    返回 (大小, 方案)，方案是升序元组。
    """
    _check_tree(tree)
    nodes = tree.vertices()
    best = None
    for subset in enumerate_subsets(nodes):
        if is_dominating_set(tree, subset):
            if best is None or (len(subset), subset) < (len(best), best):
                best = subset
    return (len(best), best)


def min_vertex_cover(tree):
    """最小点覆盖：枚举全部子集，按大小取最小，并列时按顶点集合字典序取最小。

    返回 (大小, 方案)，方案是升序元组。
    """
    _check_tree(tree)
    nodes = tree.vertices()
    best = None
    for subset in enumerate_subsets(nodes):
        if is_vertex_cover(tree, subset):
            if best is None or (len(subset), subset) < (len(best), best):
                best = subset
    return (len(best), best)


def max_independent_set(tree):
    """最大独立集：枚举全部子集，按大小取最大，并列时按顶点集合字典序取最小。

    返回 (大小, 方案)，方案是升序元组。
    """
    _check_tree(tree)
    nodes = tree.vertices()
    best = None
    for subset in enumerate_subsets(nodes):
        if is_independent_set(tree, subset):
            if best is None or (-len(subset), subset) < (-len(best), best):
                best = subset
    return (len(best), best)


def subset_check_count(tree):
    """报出 baseline 求一次最小支配集要检查多少个子集，也就是二的节点数次方。"""
    _check_tree(tree)
    return 1 << len(tree.vertices())


def weighted_min_dominating_set(tree, weight_map=None):
    """带点权的最小支配集：枚举子集，按选中顶点的点权之和取最小。

    并列时按顶点集合字典序取最小。点权可以为零或负数，缺省全为 1。
    返回 (总点权, 方案)。
    """
    _check_tree(tree)
    weights = _weight_map_of(tree, weight_map)
    nodes = tree.vertices()
    best = None
    best_cost = None
    for subset in enumerate_subsets(nodes):
        if is_dominating_set(tree, subset):
            cost = sum(weights[node] for node in subset)
            if best is None or (cost, subset) < (best_cost, best):
                best = subset
                best_cost = cost
    return (best_cost, best)


def max_weight_independent_set(tree, weight_map=None):
    """带点权的最大独立集（最大权独立集）：枚举子集，按选中顶点的点权之和取最大。

    并列时按顶点集合字典序取最小。点权可以为零或负数，缺省全为 1。
    返回 (总点权, 方案)。
    """
    _check_tree(tree)
    weights = _weight_map_of(tree, weight_map)
    nodes = tree.vertices()
    best = None
    best_cost = None
    for subset in enumerate_subsets(nodes):
        if is_independent_set(tree, subset):
            cost = sum(weights[node] for node in subset)
            if best is None or (-cost, subset) < (-best_cost, best):
                best = subset
                best_cost = cost
    return (best_cost, best)
