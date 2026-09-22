"""本地文档库。

文档按主键放在内存里，可以新增、覆盖、删除；search 是精确匹配，
每次调用都把库里的文档整扫一遍，按主键排序返回。
"""

from .text import tokens


class DocLibrary:
    """工单知识库的文档集合。"""

    def __init__(self):
        self._docs = {}
        self._subscribers = []
        self._adds = 0
        self._removes = 0
        self._searches = 0
        self._scanned = 0

    def add(self, doc_id, text):
        """写入文档，返回是否新主键。

        主键已存在时按覆盖处理，返回 False。
        """
        if not isinstance(doc_id, str) or not doc_id:
            raise ValueError("doc_id 必须是非空字符串")
        if not isinstance(text, str):
            raise ValueError("text 必须是字符串")
        old = self._docs.get(doc_id)
        self._docs[doc_id] = text
        self._adds += 1
        self._notify(doc_id, old, text)
        return old is None

    def remove(self, doc_id):
        """按主键删除，删掉返回 True，本来就没有返回 False。"""
        if doc_id not in self._docs:
            return False
        old = self._docs.pop(doc_id)
        self._removes += 1
        self._notify(doc_id, old, None)
        return True

    def get(self, doc_id):
        """取文档文本，不存在给 None。"""
        return self._docs.get(doc_id)

    def ids(self):
        """全部主键，排序列表。"""
        return sorted(self._docs)

    def count(self):
        """文档篇数。"""
        return len(self._docs)

    def scan(self):
        """按主键排序给 [(doc_id, text), ...]。"""
        return [(doc_id, self._docs[doc_id]) for doc_id in sorted(self._docs)]

    def search(self, term):
        """精确匹配：term 切出的每个 token 都出现在文档里才算命中。

        全量扫描，按主键排序返回命中的 id 列表。term 切不出 token 时
        直接给空列表。
        """
        wanted = tokens(term)
        if not wanted:
            return []
        hits = []
        for doc_id in sorted(self._docs):
            self._scanned += 1
            bag = set(tokens(self._docs[doc_id]))
            if all(word in bag for word in wanted):
                hits.append(doc_id)
        self._searches += 1
        return hits

    def stats(self):
        """当前计数：篇数与累计的写、删、查询、扫描次数。"""
        return {
            "docs": len(self._docs),
            "adds": self._adds,
            "removes": self._removes,
            "searches": self._searches,
            "scanned": self._scanned,
        }

    def subscribe(self, cb):
        """挂一个回调，写入、覆盖、删除时同步调用。

        回调签名 cb(doc_id, old_text, new_text)；新增时 old_text 为 None，
        删除时 new_text 为 None。针对未收录主键的 remove 不会触发回调。
        """
        self._subscribers.append(cb)

    def unsubscribe(self, cb):
        """摘掉之前挂上的回调，没挂过也不报错。"""
        try:
            self._subscribers.remove(cb)
        except ValueError:
            pass

    def _notify(self, doc_id, old, new):
        for cb in list(self._subscribers):
            cb(doc_id, old, new)
