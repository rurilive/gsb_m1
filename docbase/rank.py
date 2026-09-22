"""BM25 相关度排序索引。

DocLibrary 的 search 是全量扫描的精确匹配，这里提供按相关度出结果
的索引：构造时收下整个库并挂上回调，之后库里每篇文档的增删改都
同步维护倒排与长度统计，单篇开销不随库规模上涨。

排序口径：

- 切词：中文段取相邻二字组（段长为一时保留这个单字），英文数字
  按段切并转小写，查询词去重；
- 打分：标准 BM25，k1 / b 默认 1.5 / 0.75，
  idf = ln((N - df + 0.5) / (df + 0.5) + 1)；
- 名次：分数高的在前，同分按 id 字典序。

查询时按 idf 从高到低处理倒排表，只给仍有可能进前 k 的文档打分；
剩下的文档用各词项的分数上界估出总分上限，够不着当前第 k 名就整
批跳过。stats() 里的 scored 记录累计打分次数。
"""

import heapq
import math
import re
from collections import Counter

from .text import chunks

_WORD_RE = re.compile(r"[a-z0-9]+")


def rank_tokens(text):
    """排序口径的切词：中文相邻二字组，英文数字按段，全转小写。"""
    words = []
    for kind, segment in chunks(text.casefold()):
        if kind == "cjk":
            if len(segment) == 1:
                words.append(segment)
            else:
                words.extend(segment[i:i + 2] for i in range(len(segment) - 1))
        else:
            words.extend(_WORD_RE.findall(segment))
    return words


class _ReverseId(str):
    """堆内比较用：同分时让字典序大的 id 先被挤出前 k。"""

    __slots__ = ()

    def __lt__(self, other):
        return str.__gt__(self, other)


class BM25Index:
    """挂在 DocLibrary 上、随库同步的 BM25 排序索引。"""

    def __init__(self, library, k1=1.5, b=0.75):
        self.k1 = float(k1)
        self.b = float(b)
        self._library = library
        self._postings = {}
        self._tf_hist = {}
        self._dl = {}
        self._total_len = 0
        self._searches = 0
        self._scored = 0
        for doc_id, text in library.scan():
            self._index(doc_id, text)
        library.subscribe(self._on_change)

    def close(self):
        """从库上摘掉回调，之后不再跟随库的变更。"""
        if self._library is not None:
            self._library.unsubscribe(self._on_change)
            self._library = None

    def search(self, query, k=10):
        """按 BM25 给前 k 条 (doc_id, 分数)，同分按 id 字典序。"""
        terms = list(dict.fromkeys(rank_tokens(query)))
        if not terms or k <= 0 or not self._dl:
            return []
        self._searches += 1
        terms = [term for term in terms if term in self._postings]
        if not terms:
            return []
        n_docs = len(self._dl)
        avgdl = self._total_len / n_docs
        idf = {}
        bound = {}
        head = self.k1 + 1.0
        for term in terms:
            df = len(self._postings[term])
            idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
            max_tf = max(self._tf_hist[term])
            bound[term] = (
                idf[term] * head * max_tf / (max_tf + self.k1 * (1.0 - self.b))
            )
        order = sorted(terms, key=idf.__getitem__, reverse=True)
        remaining = sum(bound[term] for term in order)
        heap = []
        seen = set()
        for term in order:
            if len(heap) == k and remaining < heap[0][0]:
                break
            remaining -= bound[term]
            for doc_id in self._postings[term]:
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                self._scored += 1
                score = self._score(doc_id, terms, idf, avgdl)
                item = (score, _ReverseId(doc_id))
                if len(heap) < k:
                    heapq.heappush(heap, item)
                elif heap[0] < item:
                    heapq.heapreplace(heap, item)
        ranked = sorted(heap, key=lambda item: (-item[0], str(item[1])))
        return [(str(doc_id), score) for score, doc_id in ranked]

    def stats(self):
        """当前计数：篇数、词表大小、平均词数与累计查询、打分次数。"""
        n_docs = len(self._dl)
        return {
            "docs": n_docs,
            "terms": len(self._postings),
            "avg_len": self._total_len / n_docs if n_docs else 0.0,
            "searches": self._searches,
            "scored": self._scored,
        }

    def _score(self, doc_id, terms, idf, avgdl):
        dl = self._dl[doc_id]
        norm = self.k1 * (1.0 - self.b + self.b * dl / avgdl)
        head = self.k1 + 1.0
        total = 0.0
        for term in terms:
            tf = self._postings[term].get(doc_id)
            if tf:
                total += idf[term] * head * tf / (tf + norm)
        return total

    def _index(self, doc_id, text):
        counts = Counter(rank_tokens(text))
        self._dl[doc_id] = sum(counts.values())
        self._total_len += self._dl[doc_id]
        for term, tf in counts.items():
            self._postings.setdefault(term, {})[doc_id] = tf
            self._tf_hist.setdefault(term, Counter())[tf] += 1

    def _unindex(self, doc_id, text):
        counts = Counter(rank_tokens(text))
        self._total_len -= self._dl.pop(doc_id)
        for term, tf in counts.items():
            posting = self._postings[term]
            del posting[doc_id]
            hist = self._tf_hist[term]
            hist[tf] -= 1
            if hist[tf] == 0:
                del hist[tf]
            if not posting:
                del self._postings[term]
                del self._tf_hist[term]

    def _on_change(self, doc_id, old_text, new_text):
        if old_text is not None:
            self._unindex(doc_id, old_text)
        if new_text is not None:
            self._index(doc_id, new_text)
