"""记录库：整数 id 的记录挂一组整数标签，倒排表用 Python set 维护。"""

MAX_ID = 2 ** 32


def check_id(value, what):
    """记录 id 与标签都限定在 [0, 2**32) 的整数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s 必须是整数，收到 %r" % (what, value))
    if value < 0 or value >= MAX_ID:
        raise ValueError("%s 超出范围: %r" % (what, value))
    return value


class TagStore:
    """标签记录库。

    记录 id 是整数，add 覆盖式写入，remove 删除。每次真实变更都会通知
    订阅者，倒排表里空掉的标签当场移除，不留空壳。
    """

    def __init__(self):
        self._labels = {}        # rid -> tuple(sorted(labels))
        self._postings = {}      # label -> set(rid)
        self._subscribers = []
        self._entries = 0
        self._updates = 0

    # ---- 读写 ----
    def add(self, rid, labels=()):
        """写入记录，同 id 再写即覆盖。返回本次是否真的改了内容。"""
        check_id(rid, "记录 id")
        new = tuple(sorted(set(check_id(x, "标签") for x in labels)))
        old = self._labels.get(rid)
        if old == new:
            return False
        if old is not None:
            for label in old:
                bucket = self._postings[label]
                bucket.discard(rid)
                if not bucket:
                    del self._postings[label]
            self._entries -= len(old)
        for label in new:
            bucket = self._postings.get(label)
            if bucket is None:
                bucket = self._postings[label] = set()
            bucket.add(rid)
        self._entries += len(new)
        self._labels[rid] = new
        self._updates += 1
        self._notify(rid, old, new)
        return True

    def remove(self, rid):
        """删除记录，返回是否删掉了。删不存在的 id 是空操作。"""
        old = self._labels.pop(rid, None)
        if old is None:
            return False
        for label in old:
            bucket = self._postings[label]
            bucket.discard(rid)
            if not bucket:
                del self._postings[label]
        self._entries -= len(old)
        self._updates += 1
        self._notify(rid, old, None)
        return True

    # ---- 读取 ----
    def get(self, rid):
        """该记录的标签，按升序给出；没这个记录返回空元组。"""
        return self._labels.get(rid, ())

    def ids(self):
        """全部记录 id，升序。"""
        return sorted(self._labels)

    def count(self):
        return len(self._labels)

    def labels(self):
        """当前有倒排表的标签，升序。"""
        return sorted(self._postings)

    def postings(self, label):
        """该标签命中的记录 id 集合，返回副本，改它不影响库里状态。"""
        bucket = self._postings.get(label)
        return set(bucket) if bucket else set()

    def stats(self):
        return {
            "records": len(self._labels),
            "labels": len(self._postings),
            "entries": self._entries,
            "updates": self._updates,
        }

    # ---- 订阅 ----
    def subscribe(self, callback):
        """登记变更回调，签名是 callback(rid, old, new)。

        old / new 是变更前后的标签元组，记录原本不存在或已被删除时给 None。
        只有真正发生变更才会回调。
        """
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def _notify(self, rid, old, new):
        for callback in list(self._subscribers):
            callback(rid, old, new)
