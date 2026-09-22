"""BM25 相关度排序。

DocLibrary 的 search 仍是全量精确匹配，这里在库上叠一个 BM25Index：
构造时把库里的文档收进来建倒排，并通过 subscribe 跟随后续增删，
N、df、平均长度都随之更新，删掉的文档不会再出现在结果里。

切词口径与 text.tokens 不同：中文段取相邻二字组（段长为一时保留
该单字），英文数字仍按段切并转小写；查询词先去重再打分。打分用
标准 BM25（k1=1.5、b=0.75），IDF 取 ln((N-df+0.5)/(df+0.5)+1)，
同分按主键字典序。top-k 用 WAND 剪枝，只给有机会进前 k 的文档
打分，stats 里的 scored 记录累计打分次数。
"""

import heapq
import math
from bisect import bisect_left
from collections import Counter

from .text import _WORD_RE, chunks


def rank_tokens(text):
    """排序口径：中文段取相邻二字组，单字段保留该字；英文数字按段转小写。"""
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


class _TermState:
    """一个查询词在倒排表上的游标，postings 按主键升序。"""

    __slots__ = ("idf", "ub", "docs", "tfs", "pos")

    def __init__(self, idf, ub, docs, tfs):
        self.idf = idf
        self.ub = ub
        self.docs = docs
        self.tfs = tfs
        self.pos = 0

    def doc(self):
        return self.docs[self.pos] if self.pos < len(self.docs) else None

    def tf(self):
        return self.tfs[self.pos]

    def advance(self):
        self.pos += 1

    def seek(self, target):
        self.pos = bisect_left(self.docs, target, self.pos)


class _Cand:
    """堆里的候选，堆顶放最差的：分低者差，同分主键大者差。"""

    __slots__ = ("score", "doc_id")

    def __init__(self, score, doc_id):
        self.score = score
        self.doc_id = doc_id

    def __lt__(self, other):
        if self.score != other.score:
            return self.score < other.score
        return self.doc_id > other.doc_id


class BM25Index:
    """挂在 DocLibrary 上的 BM25 排序索引。"""

    def __init__(self, library, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self._postings = {}  # term -> {doc_id: tf}
        self._doc_len = {}  # doc_id -> 词数
        self._total_len = 0
        self._max_tf = {}  # term -> 历史最大 tf（只增不减，作安全上界）
        self._searches = 0
        self._scored = 0
        for doc_id, text in library.scan():
            self._index(doc_id, text)
        library.subscribe(self._sync)

    def search(self, query, k):
        """按 BM25 给 query 取前 k 条，返回 [(doc_id, score), ...]。

        同分按主键字典序；query 切不出词或 k 小于等于 0 时给空列表。
        """
        self._searches += 1
        if k <= 0:
            return []
        seen = set()
        terms = []
        for word in rank_tokens(query):
            if word not in seen and word in self._postings:
                seen.add(word)
                terms.append(word)
        n = len(self._doc_len)
        if not terms or n == 0:
            return []
        avgdl = self._total_len / n
        k1 = self.k1
        b = self.b

        states = []
        for word in terms:
            bucket = self._postings[word]
            df = len(bucket)
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            docs = sorted(bucket)
            # 单词贡献上界：tf 取历史最大、文档长按 0 算，只偏松不会漏。
            tf_max = self._max_tf[word]
            ub = idf * (tf_max * (k1 + 1.0)) / (tf_max + k1 * (1.0 - b))
            states.append(_TermState(idf, ub, docs, [bucket[d] for d in docs]))

        heap = []
        threshold = 0.0
        active = states
        while active:
            active.sort(key=lambda st: st.doc())
            cumulative = 0.0
            pivot = -1
            for i, st in enumerate(active):
                cumulative += st.ub
                if cumulative > threshold:
                    pivot = i
                    break
            if pivot < 0:
                break
            pivot_doc = active[pivot].doc()
            if active[0].doc() == pivot_doc:
                norm = k1 * (1.0 - b + b * self._doc_len[pivot_doc] / avgdl)
                score = 0.0
                # 固定按查询词顺序累加，与暴力打分的浮点口径一致。
                for st in states:
                    if st.doc() == pivot_doc:
                        tf = st.tf()
                        score += st.idf * (tf * (k1 + 1.0)) / (tf + norm)
                        st.advance()
                self._scored += 1
                cand = _Cand(score, pivot_doc)
                if len(heap) < k:
                    heapq.heappush(heap, cand)
                elif heap[0] < cand:
                    heapq.heapreplace(heap, cand)
                if len(heap) == k:
                    threshold = heap[0].score
            else:
                for st in active[:pivot]:
                    if st.doc() < pivot_doc:
                        st.seek(pivot_doc)
            active = [st for st in active if st.doc() is not None]

        return sorted(
            ((c.doc_id, c.score) for c in heap), key=lambda item: (-item[1], item[0])
        )

    def stats(self):
        """当前计数：篇数、词表大小与累计的查询、打分次数。"""
        return {
            "docs": len(self._doc_len),
            "terms": len(self._postings),
            "searches": self._searches,
            "scored": self._scored,
        }

    def _sync(self, doc_id, old, new):
        if old is not None:
            self._deindex(doc_id, old)
        if new is not None:
            self._index(doc_id, new)

    def _index(self, doc_id, text):
        terms = rank_tokens(text)
        self._doc_len[doc_id] = len(terms)
        self._total_len += len(terms)
        for term, tf in Counter(terms).items():
            self._postings.setdefault(term, {})[doc_id] = tf
            if tf > self._max_tf.get(term, 0):
                self._max_tf[term] = tf

    def _deindex(self, doc_id, text):
        terms = rank_tokens(text)
        self._total_len -= len(terms)
        del self._doc_len[doc_id]
        for term in set(terms):
            bucket = self._postings[term]
            del bucket[doc_id]
            if not bucket:
                del self._postings[term]
                del self._max_tf[term]
