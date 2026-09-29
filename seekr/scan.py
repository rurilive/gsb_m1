"""seekr 的朴素子串扫描实现（改造前的现状）。

现在只有一条检索路径：把每个文档的原文拿出来，用 str.find 从头到尾
找一个子串，命中就收下这个文档名。没有分词，没有倒排，没有位置。
倒排索引、布尔检索、短语检索、评分排序与词项位置见任务描述。
"""


class Corpus:
    """一撮带名字的文档，检索只有子串包含这一种。"""

    def __init__(self):
        self._docs = {}
        self._order = []

    def add(self, doc_id, text):
        """加入一篇文档，文档名不能重复，返回文档名。"""
        if not isinstance(doc_id, str) or doc_id == "":
            raise ValueError("doc_id must be a non-empty str")
        if not isinstance(text, str):
            raise ValueError("text must be a str")
        if doc_id in self._docs:
            raise ValueError("duplicate doc_id: %s" % doc_id)
        self._docs[doc_id] = text
        self._order.append(doc_id)
        return doc_id

    def remove(self, doc_id):
        """按文档名删掉一篇文档，名字不存在就报 KeyError。"""
        if doc_id not in self._docs:
            raise KeyError(doc_id)
        del self._docs[doc_id]
        self._order.remove(doc_id)

    def doc_ids(self):
        """按加入顺序返回所有文档名。"""
        return tuple(self._order)

    def text(self, doc_id):
        """取回某篇文档的原文。"""
        if doc_id not in self._docs:
            raise KeyError(doc_id)
        return self._docs[doc_id]

    def __len__(self):
        return len(self._docs)

    def __contains__(self, doc_id):
        return doc_id in self._docs

    def search(self, needle):
        """返回原文里含 needle 子串的文档名，按加入顺序，大小写敏感。"""
        if not isinstance(needle, str):
            raise ValueError("needle must be a str")
        if needle == "":
            raise ValueError("needle must not be empty")
        hits = []
        for doc_id in self._order:
            if self._docs[doc_id].find(needle) != -1:
                hits.append(doc_id)
        return hits

    def count(self, needle):
        """needle 在所有文档原文里出现的总次数，不重叠计数。"""
        if not isinstance(needle, str):
            raise ValueError("needle must be a str")
        if needle == "":
            raise ValueError("needle must not be empty")
        total = 0
        for doc_id in self._order:
            total += self._docs[doc_id].count(needle)
        return total
