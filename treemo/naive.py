"""异常层次、建树工具与基线朴素路径查询：沿父指针回升拼出路径，再逐点扫。"""


class QueryError(Exception):
    """本包所有异常的基类。"""


class InvalidNodeError(QueryError):
    """端点下标越界或不属于本树。"""


class InvalidArgumentError(QueryError):
    """构造或调用参数非法。"""


def build_tree(node_count, parents, weights):
    """把父指针数组与点权数组规整成字典。

    parents[0] 置 -1 表示根；parents[i] 是 i 的父亲。点权原样保留，
    允许为零或负数。返回 {"n", "parent", "weight", "children"}，
    children 按升序排列以保证确定性。
    """
    if node_count < 1:
        raise InvalidNodeError("节点数必须为正")
    if len(parents) != node_count or len(weights) != node_count:
        raise InvalidNodeError("父指针或点权长度与节点数不符")
    parent = [-1] * node_count
    weight = [0] * node_count
    children = [[] for _ in range(node_count)]
    for i in range(node_count):
        p = parents[i]
        if i == 0:
            if p not in (-1, 0):
                raise InvalidNodeError("根节点的父指针必须是 -1")
            parent[i] = -1
        else:
            if p < 0 or p >= node_count:
                raise InvalidNodeError("父指针越界：%r" % (p,))
            parent[i] = p
        weight[i] = int(weights[i])
    for i in range(1, node_count):
        children[parent[i]].append(i)
    for c in children:
        c.sort()
    return {"n": node_count, "parent": parent, "weight": weight, "children": children}


def node_path(tree, u, v):
    """朴素地沿父指针回升，返回 u 到 v 的顶点序列（含两端）。"""
    n = tree["n"]
    for x in (u, v):
        if not (0 <= x < n):
            raise InvalidNodeError("端点越界：%r" % (x,))
    parent = tree["parent"]
    up_u = [u]
    pos = {u: 0}
    cur = u
    while cur != 0:
        cur = parent[cur]
        pos[cur] = len(up_u)
        up_u.append(cur)
    chain = [v]
    cur = v
    while cur not in pos:
        cur = parent[cur]
        chain.append(cur)
    meet = cur
    lca_index = pos[meet]
    nodes = up_u[: lca_index + 1] + chain[::-1][1:]
    return nodes


class PathQuerier:
    """朴素树上路径查询器，四条口径都靠逐点扫，规模一大就慢。"""

    def __init__(self, node_count, parents, weights):
        self.tree = build_tree(node_count, parents, weights)
        self.weight = list(self.tree["weight"])
        self.steps = 0

    # -- 内部工具 --------------------------------------------------------
    def _check(self, x):
        if not (0 <= x < self.tree["n"]):
            raise InvalidNodeError("端点越界：%r" % (x,))

    def _path(self, u, v):
        self._check(u)
        self._check(v)
        nodes = node_path(self.tree, u, v)
        self.steps += len(nodes)
        return nodes

    # -- 能力一：路径上不同权值个数 -------------------------------------
    def path_distinct(self, u, v):
        nodes = self._path(u, v)
        seen = set()
        for x in nodes:
            seen.add(self.weight[x])
        return len(seen)

    # -- 能力二：路径权值和 ---------------------------------------------
    def path_sum(self, u, v):
        nodes = self._path(u, v)
        total = 0
        for x in nodes:
            total += self.weight[x]
        return total

    # -- 能力三：路径最大值 ---------------------------------------------
    def path_max(self, u, v):
        nodes = self._path(u, v)
        best = self.weight[nodes[0]]
        for x in nodes:
            if self.weight[x] > best:
                best = self.weight[x]
        return best

    # -- 能力四：路径上某权值出现次数 -----------------------------------
    def path_count(self, u, v, value):
        nodes = self._path(u, v)
        hit = 0
        for x in nodes:
            if self.weight[x] == int(value):
                hit += 1
        return hit

    # -- 派生：路径上出现次数最多的权值 ---------------------------------
    def path_mode(self, u, v):
        """路径上出现次数最多的权值；并列时取权值最小的那一个。"""
        nodes = self._path(u, v)
        freq = {}
        for x in nodes:
            w = self.weight[x]
            freq[w] = freq.get(w, 0) + 1
        best_value = None
        best_count = -1
        for w in sorted(freq):
            if freq[w] > best_count:
                best_count = freq[w]
                best_value = w
        return best_value

    # -- 汇总：一批查询的总核对值 ---------------------------------------
    def run(self, queries):
        """对一批查询逐条回答，返回每条结果与一个总核对值。

        每条查询形如 (u, v, value)。总核对值为各条结果的
        (序号乘结果加一) 之和，口径固定以保证确定性。
        """
        results = []
        checksum = 0
        for index, query in enumerate(queries):
            u, v, value = query
            item = {
                "distinct": self.path_distinct(u, v),
                "sum": self.path_sum(u, v),
                "max": self.path_max(u, v),
                "count": self.path_count(u, v, value),
            }
            results.append(item)
            checksum += (index + 1) * item["distinct"] + item["sum"] + item["max"]
        return results, checksum

    # -- 派生：逐点走步数 -----------------------------------------------
    def walk_steps(self, u, v):
        """显式统计从 u 与 v 两端逐级走到汇合点的步数，用于规模对照。"""
        self._check(u)
        self._check(v)
        parent = self.tree["parent"]
        depth = _depths(self.tree)
        total = 0
        a, b = u, v
        while a != b:
            if depth[a] >= depth[b]:
                a = parent[a]
            else:
                b = parent[b]
            total += 1
            self.steps += 1
        return total


def _depths(tree):
    parent = tree["parent"]
    n = tree["n"]
    depth = [0] * n
    for i in range(n):
        d = 0
        cur = i
        while cur != 0:
            cur = parent[cur]
            d += 1
        depth[i] = d
    return depth


def step_count(querier, u, v):
    """便捷函数：返回一次路径查询累计的逐步步数。"""
    before = querier.steps
    querier.path_distinct(u, v)
    return querier.steps - before
