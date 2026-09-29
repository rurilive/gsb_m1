"""gclab 的朴素堆实现（改造前的现状）。

整个库只有引用计数一条路：每次分配得到一个对象，对象里挂一个引用字典，
每加一条引用就把被指对象的计数加一，每解除一条就把计数减一，计数掉到零
就当场回收，把它持有的引用逐条断开。对象与引用都是普通的字典和列表，
没有标记阶段，没有清扫阶段，没有分代，也没有终结器与弱引用。

上面的那些见任务描述。
"""


class GCError(Exception):
    """gclab 的异常基类，后续所有具体异常都从它派生。"""


class RefCountHeap:
    """引用计数式堆：计数归零立即回收，处理不了环。

    只维护对象表本身，环里的对象互相引用，计数永远掉不到零，因此会泄漏。
    """

    def __init__(self):
        self._objects = {}
        self._refs = {}
        self._roots = set()
        self._next_id = 0
        self._collected = 0

    def alloc(self, payload=None):
        """分配一个对象，返回它的编号，初始计数为零。"""
        oid = self._next_id
        self._next_id += 1
        self._objects[oid] = payload
        self._refs[oid] = {}
        return oid

    def has_object(self, oid):
        """对象是否还在堆里。"""
        return oid in self._objects

    def payload(self, oid):
        """取对象携带的用户数据，对象不在则抛 GCError。"""
        self._require(oid)
        return self._objects[oid]

    def objects(self):
        """按分配顺序返回当前存活的对象编号。"""
        return tuple(sorted(self._objects))

    def add_root(self, oid):
        """把对象登记为根，根在计数里额外记一份外部引用。"""
        self._require(oid)
        if oid in self._roots:
            return
        self._roots.add(oid)
        self._incref(oid)

    def remove_root(self, oid):
        """取消根登记，撤掉那份外部引用。"""
        self._require(oid)
        if oid not in self._roots:
            return
        self._roots.discard(oid)
        self._decref(oid)

    def roots(self):
        """按登记顺序返回全部根对象。"""
        return tuple(sorted(self._roots))

    def add_ref(self, src, dst):
        """给 src 加一条指向 dst 的引用，dst 计数加一。"""
        self._require(src, dst)
        self._refs[src][dst] = self._refs[src].get(dst, 0) + 1
        self._incref(dst)

    def remove_ref(self, src, dst):
        """撤掉 src 指向 dst 的一条引用，dst 计数减一。"""
        self._require(src, dst)
        count = self._refs[src].get(dst, 0)
        if count <= 0:
            raise GCError("no such reference")
        if count == 1:
            del self._refs[src][dst]
        else:
            self._refs[src][dst] = count - 1
        self._decref(dst)

    def refs_of(self, oid):
        """按登记顺序返回 oid 指向的对象编号，去重。"""
        self._require(oid)
        return tuple(sorted(self._refs[oid]))

    def ref_count(self, oid):
        """对象当前的引用计数，含根那份外部引用。"""
        self._require(oid)
        return self._counts_memo(oid)

    def collected(self):
        """累计已回收的对象数。"""
        return self._collected

    def _counts_memo(self, oid):
        total = 0
        if oid in self._roots:
            total += 1
        for refs in self._refs.values():
            total += refs.get(oid, 0)
        return total

    def _incref(self, oid):
        return None

    def _decref(self, oid):
        if self._counts_memo(oid) == 0:
            self._collect(oid)

    def _collect(self, oid):
        """回收一个对象：断开它的引用，再把它从表里抹掉。"""
        if oid not in self._objects:
            return
        for dst in list(self._refs[oid]):
            self._refs[oid].clear()
            self._decref(dst)
        del self._refs[oid]
        del self._objects[oid]
        self._roots.discard(oid)
        self._collected += 1

    def _require(self, *oids):
        for oid in oids:
            if oid not in self._objects:
                raise GCError(f"unknown object: {oid!r}")
