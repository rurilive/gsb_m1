"""改造前的朴素可持久化并查集：每次合并把整张父指针数组整份拷贝。

现状口径是这样的：合并两个集合时，先把当前版本的整张父指针数组拷一份，
改掉其中若干条父指针，再把这份新数组存成一个新版本，键是新版本号。历史版本
逐个查询时，按键取出那一整份快照，在快照上顺着父指针走到根。结果虽然对，但
每次合并都要线性拷贝，历史版本一多内存就平方增长，规模一大就明显变慢。

按键与按版本号查某个结点的代表元都走同一条整份快照，另有一条每次从头重放的
独立做法，二者在同一批固定输入上逐项一致。纯标准库，无外部依赖。
"""

__all__ = [
    "PersistentDSU",
    "Erro",
    "DsuInputError",
    "UnknownElemError",
]


class Erro(Exception):
    """本模块所有异常的基类。"""


class DsuInputError(Erro):
    """元素个数或标签取值不合法。"""


class UnknownElemError(Erro):
    """查询引用了不在本结构里的元素。"""


def _check_size(n):
    """校验元素个数是合法的非负整数。"""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise DsuInputError("元素个数必须是非负整数")
    return n


def _check_labels(n, labels):
    """校验标签列表长度与元素个数一致、取值都是非空字符串。"""
    if labels is None:
        return [str(i) for i in range(n)]
    if not isinstance(labels, (list, tuple)):
        raise DsuInputError("标签必须是序列")
    if len(labels) != n:
        raise DsuInputError("标签个数与元素个数不符")
    for lb in labels:
        if not isinstance(lb, str) or not lb:
            raise DsuInputError("标签必须是非空字符串")
    return list(labels)


class PersistentDSU:
    """朴素可持久化并查集。

    版本零是初始版本：每个元素各自成集合，父指针都指向自己，名字是标签，
    集合大小都是整数一。union 在某个既有版本上合并两棵树，把版本零到该版本
    的父指针整份抄下来改好，存成一个新版本，新版本的编号是现有版本数。
    connected 与 size 在给定版本上按键取整份快照后作答。merge_count 自增，
    随每次成功合并加一。

    成功合并时固定让名字较小的一侧当静方、另一侧当动方，动方根的父指针改指
    静方根，静方根的集合大小加上动方的大小。这一口径写死，不得改动。
    """

    def __init__(self, n, labels=None):
        n = _check_size(n)
        self._n = n
        self._labels = _check_labels(n, labels)
        self._names = {lb: i for i, lb in enumerate(self._labels)}
        self._versions = [tuple(range(n))]
        self._sizes = [tuple([1] * n)]
        self._merge_count = 0

    # ------------------------------------------------------------------
    # 版本与查询
    # ------------------------------------------------------------------
    def version_count(self):
        """当前已有的版本个数，编号从零到版本数减一。"""
        return len(self._versions)

    def merge_count(self):
        """累计成功合并的次数。"""
        return self._merge_count

    def parent_of(self, version, elem):
        """取出版本 version 里 elem 的父指针编号。"""
        return self._snapshot(version)[self._resolve(elem)]

    def representative(self, version, elem):
        """取出版本 version 里 elem 的代表元编号，顺父指针走到根。"""
        parent = self._snapshot(version)
        x = self._resolve(elem)
        while parent[x] != x:
            x = parent[x]
        return x

    def connected(self, version, a, b):
        """判断版本 version 里两个元素是否在同一集合。"""
        parent = self._snapshot(version)
        ra = self._walk(parent, self._resolve(a))
        rb = self._walk(parent, self._resolve(b))
        return ra == rb

    def size(self, version, elem):
        """返回版本 version 里元素所在集合的成员个数。"""
        parent = self._snapshot(version)
        root = self._walk(parent, self._resolve(elem))
        return self._sizes[version][root]

    def members(self, version, elem):
        """返回版本 version 里元素所在集合的成员名列表副本，按名字排好序。"""
        parent = self._snapshot(version)
        root = self._walk(parent, self._resolve(elem))
        return sorted(self._labels[x] for x in range(self._n) if self._walk(parent, x) == root)

    def group_count(self, version):
        """返回版本 version 里的集合个数。"""
        return len(self.groups(version))

    def groups(self, version):
        """返回版本 version 的全部集合，每个集合是排好序的成员名列表，整体按首名排序。"""
        parent = self._snapshot(version)
        buckets = {}
        for x in range(self._n):
            buckets.setdefault(self._walk(parent, x), []).append(x)
        out = []
        for root in buckets:
            out.append(sorted(self._labels[x] for x in buckets[root]))
        out.sort()
        return out

    # ------------------------------------------------------------------
    # 合并：整份拷贝父指针后存成新版本
    # ------------------------------------------------------------------
    def union(self, version, a, b):
        """在版本 version 上合并两个元素所在的集合，返回新版本号。

        朴素做法：把该版本的整张父指针数组拷一份，改掉动方根的父指针，
        把这份改好的数组存成一个新版本。已同集合时是空操作，返回原版本号。
        """
        parent = list(self._snapshot(version))
        sizes = list(self._sizes[version])
        ia = self._resolve(a)
        ib = self._resolve(b)
        ra = self._walk_tuple(parent, ia)
        rb = self._walk_tuple(parent, ib)
        if ra == rb:
            return version
        if self._labels[ra] < self._labels[rb]:
            parent[rb] = ra
            sizes[ra] += sizes[rb]
        else:
            parent[ra] = rb
            sizes[rb] += sizes[ra]
        self._versions.append(tuple(parent))
        self._sizes.append(tuple(sizes))
        self._merge_count += 1
        return len(self._versions) - 1

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _snapshot(self, version):
        """按键取出版本 version 的整份父指针快照。"""
        if not isinstance(version, int) or isinstance(version, bool):
            raise DsuInputError("版本号必须是整数")
        if version < 0 or version >= len(self._versions):
            raise DsuInputError("版本号越界: %r" % (version,))
        return self._versions[version]

    def _walk(self, parent, x):
        """在给定快照上顺着父指针走到根。"""
        while parent[x] != x:
            x = parent[x]
        return x

    def _walk_tuple(self, parent, x):
        """在给定列表上顺着父指针走到根。"""
        while parent[x] != x:
            x = parent[x]
        return x

    def _resolve(self, elem):
        """把元素名解析成物理编号。"""
        if isinstance(elem, str) and elem in self._names:
            return self._names[elem]
        if isinstance(elem, int) and not isinstance(elem, bool) and 0 <= elem < self._n:
            return elem
        raise UnknownElemError("未知元素: %r" % (elem,))
