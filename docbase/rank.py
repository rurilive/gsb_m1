"""BM25 相关度排序索引。

挂在 DocLibrary 上：构造时把库里已有文档收进来，之后靠订阅回调
跟随增删改。内部是倒排索引（词 -> {doc_id: tf}），查询时先给最
生僻的词对应的文档打分垫高门槛，剩下的词走 WAND，够不到门槛的
文档直接跳过不打分，不会给全部命中评分。
"""

import bisect
import heapq
import math
import re

from .text import chunks

_WORD_RE = re.compile(r"[a-z0-9]+")


def rank_tokens(text):
    """排序口径的切词。

    中文段切相邻二字组，段里只剩一个字时保留这个单字；英文数字
    照旧按段切并转小写。与 text.tokens 的单字口径互不影响。
    """
    words = []
    for kind, segment in chunks(text.casefold()):
        if kind == "cjk":
            if len(segment) == 1:
                words.append(segment)
            else:
                for i in range(len(segment) - 1):
                    words.append(segment[i:i + 2])
        else:
            words.extend(_WORD_RE.findall(segment))
    return words


class _Desc:
    """包一层字符串让堆顶是字典序最大的那个 id。"""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


class BM25Index:
    """DocLibrary 的 BM25 相关度索引。

    k1、b 默认 1.5 / 0.75。构造时收库并订阅后续增删改，N、df、
    平均长度都随单篇增删增量维护，单篇开销不随库规模涨。
    """

    def __init__(self, library, k1=1.5, b=0.75):
        self.k1 = float(k1)
        self.b = float(b)
        self._library = library
        self._postings = {}  # 词 -> {doc_id: tf}
        self._tf_hist = {}   # 词 -> {tf: 篇数}，查询时取 max tf 算上界
        self._dl = {}        # doc_id -> 文档词数
        self._total_len = 0
        self._searches = 0
        self._scored = 0
        for doc_id, text in library.scan():
            self._index(doc_id, text)
        library.subscribe(self._on_change)

    def search(self, query, k=10):
        """按 BM25 给前 k 条 (doc_id, 分数)。

        分数降序，同分按 id 字典序。查询词先去重；只有至少含一个
        查询词的文档才是候选。k <= 0、空查询、空库都给空列表。
        """
        self._searches += 1
        if k <= 0:
            return []
        seen = set()
        words = []
        for word in rank_tokens(query):
            if word not in seen:
                seen.add(word)
                words.append(word)
        n_docs = len(self._dl)
        if not words or n_docs == 0:
            return []
        avg = self._total_len / n_docs
        k1p1 = self.k1 + 1.0
        terms = []
        for word in words:
            posting = self._postings.get(word)
            if not posting:
                continue
            df = len(posting)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            tf_max = max(self._tf_hist[word])
            # 单词贡献的上界：tf 取全库最大、文档长取 0。
            ub = idf * k1p1 * tf_max / (tf_max + self.k1 * (1.0 - self.b))
            items = sorted(posting.items())
            terms.append({
                "posting": posting,
                "ids": [doc_id for doc_id, _ in items],
                "pos": 0,
                "idf": idf,
                "ub": ub,
            })
        if not terms:
            return []

        heap = []  # (score, _Desc(doc_id), doc_id)，堆顶是前 k 里最差的

        # 最生僻的词命中少，先把它的文档全打分，垫高进前 k 的门槛。
        done = set()
        rarest = min(range(len(terms)), key=lambda i: len(terms[i]["ids"]))
        for doc_id in terms[rarest]["ids"]:
            self._push(heap, k, doc_id, self._score(terms, doc_id, avg))
            done.add(doc_id)
        terms[rarest]["pos"] = len(terms[rarest]["ids"])

        # WAND：按各词当前文档字典序走，累计上界够不到门槛就整段跳过。
        while True:
            terms.sort(key=lambda t: (
                t["pos"] >= len(t["ids"]),
                t["ids"][t["pos"]] if t["pos"] < len(t["ids"]) else "",
            ))
            live = 0
            for t in terms:
                if t["pos"] < len(t["ids"]):
                    live += 1
            if live == 0:
                break
            threshold = heap[0][0] if len(heap) == k else None
            cum = 0.0
            pivot = -1
            for i in range(live):
                cum += terms[i]["ub"]
                if threshold is None or cum >= threshold:
                    pivot = i
                    break
            if pivot < 0:
                break
            pivot_id = terms[pivot]["ids"][terms[pivot]["pos"]]
            if terms[0]["ids"][terms[0]["pos"]] == pivot_id:
                if pivot_id not in done:
                    done.add(pivot_id)
                    self._push(heap, k, pivot_id, self._score(terms, pivot_id, avg))
                for t in terms:
                    if t["pos"] < len(t["ids"]) and t["ids"][t["pos"]] == pivot_id:
                        t["pos"] += 1
                    else:
                        break
            else:
                for i in range(pivot):
                    t = terms[i]
                    t["pos"] = bisect.bisect_left(t["ids"], pivot_id, t["pos"])

        out = sorted(heap, key=lambda e: (-e[0], e[2]))
        return [(doc_id, score) for score, _, doc_id in out]

    def stats(self):
        """当前计数：篇数、词表大小、平均文档长、累计查询与打分次数。"""
        n_docs = len(self._dl)
        return {
            "docs": n_docs,
            "terms": len(self._postings),
            "avg_len": self._total_len / n_docs if n_docs else 0.0,
            "searches": self._searches,
            "scored": self._scored,
        }

    def _on_change(self, doc_id, old, new):
        if old is not None:
            self._deindex(doc_id, old)
        if new is not None:
            self._index(doc_id, new)

    def _index(self, doc_id, text):
        counts = {}
        for word in rank_tokens(text):
            counts[word] = counts.get(word, 0) + 1
        length = 0
        for word, tf in counts.items():
            length += tf
            posting = self._postings.get(word)
            if posting is None:
                posting = self._postings[word] = {}
            posting[doc_id] = tf
            hist = self._tf_hist.get(word)
            if hist is None:
                hist = self._tf_hist[word] = {}
            hist[tf] = hist.get(tf, 0) + 1
        self._dl[doc_id] = length
        self._total_len += length

    def _deindex(self, doc_id, text):
        counts = {}
        for word in rank_tokens(text):
            counts[word] = counts.get(word, 0) + 1
        length = 0
        for word, tf in counts.items():
            length += tf
            posting = self._postings[word]
            del posting[doc_id]
            hist = self._tf_hist[word]
            left = hist[tf] - 1
            if left:
                hist[tf] = left
            else:
                del hist[tf]
            if not posting:
                del self._postings[word]
                del self._tf_hist[word]
        del self._dl[doc_id]
        self._total_len -= length

    def _score(self, terms, doc_id, avg):
        self._scored += 1
        dl = self._dl[doc_id]
        norm = self.k1 * (1.0 - self.b + self.b * dl / avg)
        k1p1 = self.k1 + 1.0
        total = 0.0
        for t in terms:
            tf = t["posting"].get(doc_id)
            if tf:
                total += t["idf"] * tf * k1p1 / (tf + norm)
        return total

    def _push(self, heap, k, doc_id, score):
        entry = (score, _Desc(doc_id), doc_id)
        if len(heap) < k:
            heapq.heappush(heap, entry)
        elif score > heap[0][0] or (score == heap[0][0] and doc_id < heap[0][2]):
            heapq.heapreplace(heap, entry)
