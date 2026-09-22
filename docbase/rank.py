"""BM25 相关度排序索引。

DocLibrary.search 是精确匹配的全量扫描，库大了以后顶不住；这里
提供按相关度出结果的索引。构造时收下整个库，之后靠库的订阅回调
增量跟进：增、删、覆盖都会同步维护倒排表、文档频率与平均长度，
单篇增删的开销只跟这篇文档自己的词数有关，不随库规模涨。

切词口径与 text.tokens 不同：中文段取相邻二字组（段里只剩一字时
保留这个单字），英文数字段照旧切小写词。查询词去重后按标准 BM25
打分：

    score(d) = sum_t idf(t) * tf*(k1+1) / (tf + k1*(1-b+b*dl/avgdl))
    idf(t)   = ln((N - df + 0.5) / (df + 0.5) + 1)

同分按 doc_id 字典序。查询时先用各查询词的上界分（idf*(k1+1)，
因为 tf 归一项永远不超过 k1+1）给候选文档攒出总分上界，按上界
从高到低精确打分，一旦当前第 k 名的分数已经超过剩余候选的上界
就停，命中的文档不会全部打分；stats() 里的 scored 记录精确打分
的次数。
"""

import math
from bisect import insort
from collections import Counter

from .text import _WORD_RE, chunks


def rank_tokens(text):
    """排序口径的切词：中文段取相邻二字组，单字段保留单字。"""
    words = []
    for kind, segment in chunks(text.casefold()):
        if kind == "cjk":
            if len(segment) == 1:
                words.append(segment)
            else:
                words.extend(segment[i : i + 2] for i in range(len(segment) - 1))
        else:
            words.extend(_WORD_RE.findall(segment))
    return words


class BM25Index:
    """挂在 DocLibrary 上的 BM25 排序索引。"""

    def __init__(self, library, k1=1.5, b=0.75):
        self.k1 = float(k1)
        self.b = float(b)
        self._library = library
        self._postings = {}  # term -> {doc_id: tf}
        self._doc_terms = {}  # doc_id -> [term, ...]
        self._doc_len = {}  # doc_id -> 词数
        self._total_len = 0
        self._searches = 0
        self._candidates = 0
        self._scored = 0
        for doc_id, text in library.scan():
            self._index_doc(doc_id, text)
        library.subscribe(self._on_change)

    def close(self):
        """摘掉挂在库上的回调，之后不再跟进库的变更。"""
        self._library.unsubscribe(self._on_change)

    def search(self, query, k):
        """按 BM25 给前 k 条 [(doc_id, 分数), ...]，同分按 id 字典序。"""
        self._searches += 1
        if k <= 0:
            return []
        qterms = list(dict.fromkeys(rank_tokens(query)))
        n = len(self._doc_len)
        if not qterms or n == 0:
            return []
        avgdl = self._total_len / n
        terms = []
        for term in qterms:
            posting = self._postings.get(term)
            if posting:
                df = len(posting)
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
                terms.append((posting, idf))
        if not terms:
            return []
        k1 = self.k1
        b = self.b
        # 每个词的上界分：tf 归一项 tf*(k1+1)/(tf+k1*(...)) 恒小于 k1+1。
        bounds = {}
        for posting, idf in terms:
            ub = idf * (k1 + 1.0)
            for doc_id in posting:
                bounds[doc_id] = bounds.get(doc_id, 0.0) + ub
        self._candidates += len(bounds)
        ordered = sorted(bounds.items(), key=lambda kv: (-kv[1], kv[0]))
        doc_len = self._doc_len
        top = []  # 有序列表，元素 (-score, doc_id)，最好的在前，至多 k 条
        scores = {}
        tau = None  # 当前第 k 名的分数，没攒够 k 条时为 None
        for doc_id, ub in ordered:
            if tau is not None and ub < tau:
                break
            dl = doc_len[doc_id]
            norm = k1 * (1.0 - b + b * dl / avgdl)
            score = 0.0
            for posting, idf in terms:
                tf = posting.get(doc_id)
                if tf:
                    score += idf * tf * (k1 + 1.0) / (tf + norm)
            self._scored += 1
            scores[doc_id] = score
            insort(top, (-score, doc_id))
            if len(top) > k:
                del top[-1]
            tau = -top[-1][0] if len(top) == k else None
        return [(doc_id, scores[doc_id]) for _neg, doc_id in top]

    def stats(self):
        """当前计数：篇数、词表大小、平均长度与累计查询、候选、打分次数。"""
        n = len(self._doc_len)
        return {
            "docs": n,
            "terms": len(self._postings),
            "avgdl": self._total_len / n if n else 0.0,
            "searches": self._searches,
            "candidates": self._candidates,
            "scored": self._scored,
        }

    def _on_change(self, doc_id, old, new):
        if old is not None:
            self._unindex_doc(doc_id)
        if new is not None:
            self._index_doc(doc_id, new)

    def _index_doc(self, doc_id, text):
        tf = Counter(rank_tokens(text))
        self._doc_terms[doc_id] = list(tf)
        self._doc_len[doc_id] = sum(tf.values())
        self._total_len += self._doc_len[doc_id]
        for term, count in tf.items():
            self._postings.setdefault(term, {})[doc_id] = count

    def _unindex_doc(self, doc_id):
        terms = self._doc_terms.pop(doc_id)
        self._total_len -= self._doc_len.pop(doc_id)
        for term in terms:
            posting = self._postings[term]
            del posting[doc_id]
            if not posting:
                del self._postings[term]
