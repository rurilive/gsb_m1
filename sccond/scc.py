"""sccond.scc —— 有向图连通性工具的朴素基线（改造前）。

包内只有一层朴素实现：求强连通分量靠对每一对顶点各跑一次可达搜索来判断
是否互达；缩点、拓扑序、最长链，以及整图强连通判断、分量间可达、某点可达
的最大分量，也都建立在反复的可达搜索之上。规模一大就慢，但结果正确。

顶点只要求可哈希且可排序，本模块不解释顶点含义。全部实现只用标准库。
"""


class GraphError(Exception):
    """本包全部错误的基类。"""


class UnknownVertexError(GraphError):
    """访问了尚未加入本图的顶点。"""


class Digraph:
    """有向图，邻接表保存；自环允许，重边自动去重。"""

    def __init__(self, vertices=None):
        self._adj = {}
        self.reset_counters()
        if vertices is not None:
            for v in vertices:
                self.add_vertex(v)

    # ---- 计数（用于规模对照） ----

    def reset_counters(self):
        """清零可达搜索计数。"""
        self._search_runs = 0
        self._visit_count = 0

    def counters(self):
        """返回可达到搜索的次数与访问过的顶点次数。"""
        return {"search_runs": self._search_runs, "visit_count": self._visit_count}

    # ---- 构造 ----

    def add_vertex(self, v):
        self._adj.setdefault(v, set())
        return v

    def add_edge(self, u, w):
        """加一条有向边 u 到 w，两端顶点自动加入；重边只留一条。"""
        self.add_vertex(u)
        self.add_vertex(w)
        self._adj[u].add(w)
        return (u, w)

    # ---- 查询 ----

    def vertices(self):
        """全部顶点，升序。"""
        return sorted(self._adj)

    def neighbors(self, v):
        """v 的出边邻居，升序去重。"""
        self._require(v)
        return sorted(self._adj[v])

    def out_degree(self, v):
        self._require(v)
        return len(self._adj[v])

    def edge_count(self):
        return sum(len(s) for s in self._adj.values())

    def _require(self, v):
        if v not in self._adj:
            raise UnknownVertexError(f"顶点未加入本图: {v!r}")

    # ---- 朴素可达 ----

    def reachable_set(self, v):
        """从 v 出发一次深度优先搜索，返回可达顶点（含 v 自身），升序。"""
        self._require(v)
        self._search_runs += 1
        seen = set()
        stack = [v]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            self._visit_count += 1
            for w in sorted(self._adj[cur]):
                if w not in seen:
                    stack.append(w)
        return tuple(sorted(seen))

    def reachable(self, a, b):
        """a 是否可达 b；a 到自身视为可达。"""
        self._require(a)
        self._require(b)
        return b in self.reachable_set(a)

    def mutually_reachable(self, a, b):
        """a 与 b 是否互达；同一点视为互达。"""
        self._require(a)
        self._require(b)
        if a == b:
            return True
        return self.reachable(a, b) and self.reachable(b, a)

    # ---- 朴素强连通分量 ----

    def components(self):
        """把顶点划成强连通分量。

        对每个尚未归类的顶点，与其余每个顶点逐一做一次互达判断，把与之
        互达的顶点收进同一块。分量本身按最小顶点升序排列，块内同样升序。
        """
        vs = self.vertices()
        seen = set()
        comps = []
        for v in vs:
            if v in seen:
                continue
            comp = [u for u in vs if self.mutually_reachable(v, u)]
            for u in comp:
                seen.add(u)
            comps.append(tuple(sorted(comp)))
        comps.sort(key=lambda c: c[0])
        return comps

    def component_count(self):
        return len(self.components())

    def component_of(self, v):
        """v 所属的分量（按最小顶点升序的分量元组）。"""
        self._require(v)
        for comp in self.components():
            if v in comp:
                return comp
        raise UnknownVertexError(f"顶点未加入本图: {v!r}")

    def is_strongly_connected(self):
        """整图是否强连通；空图按非强连通处理。"""
        vs = self.vertices()
        if not vs:
            return False
        return all(self.mutually_reachable(vs[0], u) for u in vs)

    # ---- 朴素缩点 ----

    def condensation(self):
        """把每个分量缩成一个点，返回无环的缩点图。

        缩点图的顶点是分量编号，编号按分量最小顶点升序从零开始；从分量 i
        到 j 的边存在当且仅当原图里有一条从 i 的顶点到 j 的顶点的边且两端
        分量不同。
        """
        comps = self.components()
        index = {}
        for i, comp in enumerate(comps):
            for v in comp:
                index[v] = i
        cg = Digraph(range(len(comps)))
        for u in self.vertices():
            for w in self.neighbors(u):
                if index[u] != index[w]:
                    cg.add_edge(index[u], index[w])
        return cg

    def topological_order(self):
        """缩点图的一个拓扑序（分量编号序列）。

        每轮在剩余分量里挑第一个没有入边的分量：判断入边对每个候选都重跑
        一遍可达搜索。缩点图本应无环，一旦挑不出即说明不可能，抛基类错误。
        """
        cg = self.condensation()
        remaining = list(cg.vertices())
        order = []
        while remaining:
            pick = None
            for v in remaining:
                has_incoming = False
                for u in remaining:
                    if u != v and cg.reachable(u, v):
                        has_incoming = True
                        break
                if not has_incoming:
                    pick = v
                    break
            if pick is None:
                raise GraphError("缩点图出现环，无法给出拓扑序")
            order.append(pick)
            remaining.remove(pick)
        return order

    def longest_chain(self):
        """缩点图里最长链的边数，以及其中一条最长链（分量编号序列）。

        朴素地枚举缩点图里的每一条简单路径，取最长的一条；并列时保留先枚举
        到的那条，因而结果只由编号升序遍历决定。
        """
        cg = self.condensation()
        best = []

        def walk(path):
            nonlocal best
            if len(path) > len(best):
                best = list(path)
            for w in cg.neighbors(path[-1]):
                if w not in path:
                    walk(path + [w])

        for v in cg.vertices():
            walk([v])
        if not best:
            return (0, [])
        return (len(best) - 1, best)

    def source_components(self):
        """入度为零的分量编号，升序。"""
        cg = self.condensation()
        vs = cg.vertices()
        out = []
        for v in vs:
            incoming = any(u != v and cg.reachable(u, v) for u in vs)
            if not incoming:
                out.append(v)
        return out

    def sink_components(self):
        """出度为零的分量编号，升序。"""
        cg = self.condensation()
        ds = cg.vertices()
        out = []
        for v in ds:
            if cg.out_degree(v) == 0:
                out.append(v)
        return out

    # ---- 朴素分量间可达与统计 ----

    def reachable_components(self, v):
        """从 v 出发能到达的全部分量编号，升序（含 v 自身所在分量）。

        先求 v 的可达顶点集合，再把顶点映射成分量：由于分量内部强连通，
        只要能到达分量里一个点，就能到达该分量全部点，二者等价。
        """
        comps = self.components()
        index = {}
        for i, comp in enumerate(comps):
            for u in comp:
                index[u] = i
        return tuple(sorted({index[u] for u in self.reachable_set(v)}))

    def transitive_closure(self):
        """每个顶点到其余顶点的可达关系，逐点做一次可达搜索得到。"""
        return {v: self.reachable_set(v) for v in self.vertices()}

    def max_reachable_component_size(self, v):
        """v 所能到达的分量中，顶点数最多的分量的顶点数。

        并列时取最小顶点更小的那个分量，故结果由固定口径决定。
        """
        comps = self.components()
        reach = set(self.reachable_components(v))
        best = None
        for i in range(len(comps)):
            if i not in reach:
                continue
            key = (len(comps[i]), -comps[i][0])
            if best is None or key > best[0]:
                best = (key, len(comps[i]))
        return 0 if best is None else best[1]


def naive_pair_count(n):
    """n 个顶点时，朴素逐对互达判断需要的有序点对搜索次数上界 n 乘 n 减一。"""
    return n * (n - 1)
