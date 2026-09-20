"""内存倒排索引 + 定期全量落盘。"""
import json
import os
import tempfile

SNAPSHOT_NAME = "index.snapshot.json"
SNAPSHOT_EVERY = 100


def tokenize(text):
    """小写按空白切词，去重后排序。"""
    return sorted(set(text.lower().split()))


class IndexStore:
    """正排（doc_id -> 原文）与倒排（term -> doc_id 集合）都在内存里。"""

    def __init__(self, directory, snapshot_every=SNAPSHOT_EVERY):
        self._dir = directory
        self._snapshot_every = snapshot_every
        self._docs = {}
        self._postings = {}
        self._ops = 0
        os.makedirs(directory, exist_ok=True)

    # -- 查询 ---------------------------------------------------------
    def get(self, doc_id):
        return self._docs.get(doc_id)

    def search(self, term):
        return sorted(self._postings.get(term.lower(), ()))

    def doc_count(self):
        return len(self._docs)

    # -- 变更 ---------------------------------------------------------
    def put(self, doc_id, text):
        if doc_id in self._docs:
            self._unindex(doc_id)
        self._docs[doc_id] = text
        for term in tokenize(text):
            self._postings.setdefault(term, set()).add(doc_id)
        self._after_change()

    def delete(self, doc_id):
        if doc_id not in self._docs:
            return
        self._unindex(doc_id)
        self._after_change()

    def _unindex(self, doc_id):
        text = self._docs.pop(doc_id)
        for term in tokenize(text):
            bucket = self._postings.get(term)
            if bucket:
                bucket.discard(doc_id)
                if not bucket:
                    del self._postings[term]

    def _after_change(self):
        self._ops += 1
        if self._ops >= self._snapshot_every:
            self.snapshot()

    # -- 落盘 / 恢复 --------------------------------------------------
    def snapshot(self):
        """整份索引原子写入快照文件。"""
        payload = {"docs": self._docs, "ops": self._ops}
        fd, tmp = tempfile.mkstemp(dir=self._dir)
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, os.path.join(self._dir, SNAPSHOT_NAME))
        self._ops = 0

    def load(self):
        """从快照重建内存索引，返回载入的文档数。"""
        path = os.path.join(self._dir, SNAPSHOT_NAME)
        if not os.path.exists(path):
            return 0
        with open(path) as f:
            payload = json.load(f)
        self._docs = dict(payload["docs"])
        self._postings = {}
        for doc_id, text in self._docs.items():
            for term in tokenize(text):
                self._postings.setdefault(term, set()).add(doc_id)
        self._ops = 0
        return len(self._docs)
