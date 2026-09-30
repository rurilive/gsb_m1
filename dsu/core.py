"""dsu 的朴素不相交集合实现（改造前的现状）。

现状只走一条最直白的路：内部用代表元到成员列表的字典维护各个集合，成员逐个改名
挂到代表元下。合并两个集合时把一侧的全体成员逐个改名挂到另一侧的代表元下，查询
归属时逐个集合、逐个成员地线性扫描，带权偏移在每次搬移时逐元素重算，环检测也靠
一次线性扫描的归属查询完成。口径单一、结果确定，但每次合并与查询的代价随集合规
模线性增长。异常统一从 Erro 派生。

计数口径（对外契约，务必逐字遵守）：

- 合并次数按真实发生的合并计，一次成功合并记一次，自合并与无效合并不计。
- 查询次数只在三个对外查询入口各记一次，入口为 find、connected、relate；
  其余方法（含 union、union_weighted、add_edge 以及内部取根的私有方法）都不动
  查询计数，内部取根也不重复计数。
- 改名次数按搬移过程中被逐个改名的成员累计，扫描次数按线性扫描访问过的成员累计。
"""


class Erro(Exception):
    """本库所有对外异常的公共基类。"""


class BadElement(Erro):
    """元素编号不是非负整数。"""


class UnknownNode(Erro):
    """查询没有登记过的元素。"""


class NotConnected(Erro):
    """求相对偏移时两点不在同一个集合。"""


class BadWeight(Erro):
    """偏移不是整数。"""


class NaiveDisjointSets:
    """朴素并查集：代表元到成员列表，逐元素改名与线性扫描。

    代表元的选取由实现决定，对外只保证同集合两元素取到同一个代表元、不同集合取到
    不同的代表元，因此跨实现比对分组与连通性，不要比对具体的代表元编号。
    """

    def __init__(self):
        self._parent = {}
        self._members = {}
        self._offset = {}
        self._merges = 0
        self._queries = 0
        self._renames = 0
        self._scans = 0

    # ---- 登记 ----

    def add(self, x):
        """登记元素，幂等；重复登记不改变已有归属。"""
        if not isinstance(x, int) or isinstance(x, bool) or x < 0:
            raise BadElement("元素编号必须是非负整数: %r" % (x,))
        if x in self._parent:
            return
        self._parent[x] = x
        self._members[x] = [x]
        self._offset[x] = 0

    def contains(self, x):
        return x in self._parent

    def elements(self):
        """全部已登记元素，升序。"""
        return sorted(self._parent)

    def _check(self, x):
        if x not in self._parent:
            raise UnknownNode("未登记的元素: %r" % (x,))

    def _root(self, x):
        """内部取根：逐集合、逐成员线性扫描，不触碰查询计数。"""
        for root, members in self._members.items():
            for m in members:
                self._scans += 1
                if m == x:
                    return root
        raise Erro("内部状态不一致: %r" % (x,))

    # ---- 查询 ----

    def find(self, x):
        """返回元素所在集合的一个代表元，逐个集合、逐个成员线性扫描。"""
        self._check(x)
        self._queries += 1
        return self._root(x)

    def connected(self, a, b):
        """两点是否连通，同一点恒连通；只计一次查询。"""
        self._check(a)
        self._check(b)
        self._queries += 1
        return self._root(a) == self._root(b)

    def size(self, x):
        """集合大小，先取根再数成员。"""
        self._check(x)
        return len(self._members[self._root(x)])

    def group_members(self, x):
        """某点所在集合的全部成员，升序。"""
        self._check(x)
        return sorted(self._members[self._root(x)])

    def groups(self):
        """全部集合，每个集合成员升序，集合之间按最小成员升序。"""
        out = [sorted(ms) for ms in self._members.values()]
        out.sort(key=lambda g: g[0])
        return out

    def component_count(self):
        return len(self._members)

    def component_sizes(self):
        return sorted(len(ms) for ms in self._members.values())

    def relate(self, a, b):
        """返回 a 相对 b 的偏移，两点不同集合时抛 NotConnected；只计一次查询。"""
        self._check(a)
        self._check(b)
        self._queries += 1
        if self._root(a) != self._root(b):
            raise NotConnected("两点不在同一个集合: %r %r" % (a, b))
        return self._offset[a] - self._offset[b]

    # ---- 合并 ----

    def union(self, a, b):
        """把 b 所在集合的成员逐个改名挂到 a 所在集合的代表元下。"""
        self._check(a)
        self._check(b)
        ra = self._root(a)
        rb = self._root(b)
        if ra == rb:
            return False
        target = self._members[ra]
        for m in self._members[rb]:
            self._parent[m] = ra
            target.append(m)
            self._renames += 1
        del self._members[rb]
        self._merges += 1
        return True

    def union_weighted(self, a, b, w):
        """建立关系，令 a 相对 b 的偏移恰为 w；搬移时逐元素重算偏移。"""
        if not isinstance(w, int) or isinstance(w, bool):
            raise BadWeight("偏移必须是整数: %r" % (w,))
        self._check(a)
        self._check(b)
        ra = self._root(a)
        rb = self._root(b)
        if ra == rb:
            return False
        # 目标是合并后 offset(a) 减 offset(b) 等于 w，据此求 b 侧整份偏移的搬移量。
        k = self._offset[a] - self._offset[b] - w
        target = self._members[ra]
        for m in self._members[rb]:
            self._parent[m] = ra
            self._offset[m] = self._offset[m] + k
            target.append(m)
            self._renames += 1
        del self._members[rb]
        self._merges += 1
        return True

    # ---- 动态连通性下的环检测 ----

    def add_edge(self, u, v):
        """登记一条无向边；若两端已连通则成环，不并入并返回假，否则并入返回真。"""
        self.add(u)
        self.add(v)
        if self._root(u) == self._root(v):
            return False
        self.union(u, v)
        return True

    def would_close_cycle(self, u, v):
        """只判断再连一条边会不会成环，不改变结构；未登记元素按未连通处理。"""
        self.add(u)
        self.add(v)
        return self._root(u) == self._root(v)

    # ---- 规模计数 ----

    def count_merges(self):
        """累计真实发生的合并次数。"""
        return self._merges

    def count_queries(self):
        """累计对外查询入口的调用次数。"""
        return self._queries

    def count_renames(self):
        """累计成员改名次数。"""
        return self._renames

    def count_scans(self):
        """累计线性扫描访问过的成员次数。"""
        return self._scans

    def cost_report(self):
        return {
            "merges": self._merges,
            "queries": self._queries,
            "renames": self._renames,
            "scans": self._scans,
        }
