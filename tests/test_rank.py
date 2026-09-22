"""BM25Index 的行为与性能测试：随机语料上与暴力打分对拍。"""

import math
import random
import time
import unittest
from collections import Counter

from docbase.library import DocLibrary
from docbase.rank import BM25Index, rank_tokens

CJK = [chr(0x4E00 + i) for i in range(40)]
EN = ["w%d" % i for i in range(60)]


def make_text(rng):
    parts = []
    for _ in range(rng.randrange(1, 8)):
        if rng.random() < 0.5:
            parts.append("".join(rng.choice(CJK) for _ in range(rng.randrange(1, 7))))
        else:
            parts.append(" ".join(rng.choice(EN) for _ in range(rng.randrange(1, 4))))
    return rng.choice([" ", "，", "。"]).join(parts)


def make_query(rng):
    parts = []
    for _ in range(rng.randrange(1, 4)):
        roll = rng.random()
        if roll < 0.35:
            parts.append("".join(rng.choice(CJK) for _ in range(rng.randrange(1, 4))))
        elif roll < 0.8:
            parts.append(rng.choice(EN))
        else:
            parts.append("oov%d" % rng.randrange(1000))
    query = " ".join(parts)
    if rng.random() < 0.3:
        query = query + " " + query
    return query


def brute_force(docs, query, k, k1=1.5, b=0.75):
    """全量打分的参照实现，口径与 rank.py 里的公式一致。"""
    terms = list(dict.fromkeys(rank_tokens(query)))
    if not terms or k <= 0 or not docs:
        return []
    counters = {doc_id: Counter(rank_tokens(text)) for doc_id, text in docs.items()}
    n_docs = len(docs)
    avgdl = sum(sum(bag.values()) for bag in counters.values()) / n_docs
    idf = {}
    for term in terms:
        df = sum(1 for bag in counters.values() if term in bag)
        idf[term] = math.log((n_docs - df + 0.5) / (df + 0.5) + 1)
    scored = []
    for doc_id, bag in counters.items():
        norm = k1 * (1.0 - b + b * sum(bag.values()) / avgdl)
        total = 0.0
        for term in terms:
            tf = bag.get(term)
            if tf:
                total += idf[term] * (k1 + 1.0) * tf / (tf + norm)
        if total > 0.0:
            scored.append((doc_id, total))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:k]


class RankTokensTest(unittest.TestCase):
    def test_cjk_bigrams(self):
        self.assertEqual(rank_tokens("支付超时"), ["支付", "付超", "超时"])

    def test_single_cjk_char_kept(self):
        self.assertEqual(rank_tokens("猫"), ["猫"])
        self.assertEqual(rank_tokens("支付，猫"), ["支付", "猫"])

    def test_latin_casefolded_and_split(self):
        self.assertEqual(rank_tokens("Export Timeout-3"), ["export", "timeout", "3"])

    def test_empty(self):
        self.assertEqual(rank_tokens(""), [])
        self.assertEqual(rank_tokens("  ，。 "), [])


class BM25IndexBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.lib = DocLibrary()
        self.index = BM25Index(self.lib)

    def tearDown(self):
        self.index.close()

    def test_default_parameters(self):
        self.assertEqual(self.index.k1, 1.5)
        self.assertEqual(self.index.b, 0.75)

    def test_tie_breaks_by_doc_id(self):
        self.lib.add("b-2", "支付超时")
        self.lib.add("a-1", "支付超时")
        got = self.index.search("支付", 10)
        self.assertEqual([doc_id for doc_id, _ in got], ["a-1", "b-2"])
        self.assertAlmostEqual(got[0][1], got[1][1], places=15)

    def test_query_terms_deduped(self):
        self.lib.add("d1", "gateway timeout")
        self.lib.add("d2", "gateway only")
        self.assertEqual(
            self.index.search("timeout timeout", 5),
            self.index.search("timeout", 5),
        )

    def test_empty_query_and_bad_k(self):
        self.lib.add("d1", "abc")
        self.assertEqual(self.index.search(""), [])
        self.assertEqual(self.index.search("  ，。"), [])
        self.assertEqual(self.index.search("abc", 0), [])
        self.assertEqual(self.index.stats()["searches"], 0)

    def test_no_match_returns_nothing(self):
        self.lib.add("d1", "abc")
        self.assertEqual(self.index.search("zzz"), [])

    def test_empty_index_returns_nothing(self):
        self.assertEqual(self.index.search("abc"), [])

    def test_stats_follow_add_and_remove(self):
        self.lib.add("d1", "支付超时")
        self.lib.add("d2", "ab cd")
        stats = self.index.stats()
        self.assertEqual(stats["docs"], 2)
        self.assertEqual(stats["terms"], 5)
        self.assertAlmostEqual(stats["avg_len"], 2.5)
        self.lib.remove("d1")
        stats = self.index.stats()
        self.assertEqual(stats["docs"], 1)
        self.assertEqual(stats["terms"], 2)
        self.assertAlmostEqual(stats["avg_len"], 2.0)

    def test_removed_doc_never_shows_up(self):
        self.lib.add("d1", "支付超时排查")
        self.lib.add("d2", "支付回调")
        self.lib.remove("d1")
        got = self.index.search("支付超时", 10)
        self.assertEqual([doc_id for doc_id, _ in got], ["d2"])

    def test_reindex_uses_new_text(self):
        self.lib.add("d1", "支付超时")
        self.lib.add("d1", "网关日志")
        self.assertEqual(self.index.search("支付", 10), [])
        self.assertEqual([d for d, _ in self.index.search("网关", 10)], ["d1"])

    def test_close_stops_following_library(self):
        self.lib.add("d1", "abc")
        self.index.close()
        self.lib.add("d2", "def")
        self.assertEqual(self.index.stats()["docs"], 1)
        self.assertEqual(self.index.search("def", 10), [])

    def test_scored_counts_scoring_work(self):
        self.lib.add("d1", "支付超时")
        self.lib.add("d2", "支付回调")
        self.index.search("支付", 10)
        self.assertEqual(self.index.stats()["scored"], 2)
        self.assertEqual(self.index.stats()["searches"], 1)


class BM25VersusBruteForceTest(unittest.TestCase):
    """随机语料、随机查询下与暴力打分逐条对拍。"""

    def assert_ranking_equal(self, index, docs, query, k, k1=1.5, b=0.75):
        expected = brute_force(docs, query, k, k1=k1, b=b)
        got = index.search(query, k)
        self.assertEqual(
            [doc_id for doc_id, _ in got],
            [doc_id for doc_id, _ in expected],
            "名次不一致：query=%r k=%r" % (query, k),
        )
        for (_, got_score), (_, want_score) in zip(got, expected):
            self.assertAlmostEqual(got_score, want_score, places=12)

    def build_corpus(self, rng, n_docs):
        docs = {}
        for i in range(n_docs):
            docs["d%04d" % i] = make_text(rng)
        return docs

    def sync_library(self, docs):
        lib = DocLibrary()
        for doc_id, text in docs.items():
            lib.add(doc_id, text)
        return lib

    def test_matches_brute_force(self):
        rng = random.Random(20260922)
        docs = self.build_corpus(rng, 300)
        lib = self.sync_library(docs)
        index = BM25Index(lib)
        queries = [make_query(rng) for _ in range(30)]
        for query in queries:
            for k in (1, 3, 10, 250):
                self.assert_ranking_equal(index, docs, query, k)

        removed = set()
        ids = list(docs)
        rng.shuffle(ids)
        for doc_id in ids[: len(ids) // 2]:
            lib.remove(doc_id)
            removed.add(doc_id)
            del docs[doc_id]
        for i in range(150):
            roll = rng.random()
            if roll < 0.4:
                doc_id = "n%04d" % i
                docs[doc_id] = make_text(rng)
                lib.add(doc_id, docs[doc_id])
            elif roll < 0.7 and docs:
                doc_id = rng.choice(list(docs))
                lib.remove(doc_id)
                removed.add(doc_id)
                del docs[doc_id]
            elif docs:
                doc_id = rng.choice(list(docs))
                docs[doc_id] = make_text(rng)
                lib.add(doc_id, docs[doc_id])

        queries += [make_query(rng) for _ in range(30)]
        for query in queries:
            for k in (1, 3, 10, 250):
                self.assert_ranking_equal(index, docs, query, k)
        alive = set(docs)
        for query in queries:
            for doc_id, _ in index.search(query, 250):
                self.assertIn(doc_id, alive)
                self.assertNotIn(doc_id, removed - alive)

    def test_matches_brute_force_with_custom_parameters(self):
        rng = random.Random(7)
        docs = self.build_corpus(rng, 120)
        lib = self.sync_library(docs)
        index = BM25Index(lib, k1=1.2, b=0.5)
        for _ in range(15):
            query = make_query(rng)
            self.assert_ranking_equal(index, docs, query, 10, k1=1.2, b=0.5)


class BM25ScaleTest(unittest.TestCase):
    """十万篇、万级词表：常见词配生僻词查前二十的耗时与打分次数。"""

    def test_common_plus_rare_query(self):
        rng = random.Random(99)
        vocab = ["w%05d" % i for i in range(10000)]
        lib = DocLibrary()
        index = BM25Index(lib)
        for i in range(100000):
            words = [vocab[rng.randrange(len(vocab))] for _ in range(8)]
            if i % 10 < 3:
                words.append("timeout")
            lib.add("t%06d" % i, " ".join(words))
        for i in range(25):
            words = [vocab[rng.randrange(len(vocab))] for _ in range(8)]
            lib.add("rare%02d" % i, "xylophone " + " ".join(words))

        before = index.stats()["scored"]
        start = time.perf_counter()
        top = index.search("timeout xylophone", 20)
        elapsed = time.perf_counter() - start
        scored = index.stats()["scored"] - before
        hits = len(set(index._postings["timeout"]) | set(index._postings["xylophone"]))
        self.assertLess(elapsed, 1.0)
        self.assertLessEqual(scored, hits * 0.3)
        self.assertEqual(len(top), 20)
        self.assertTrue(all(doc_id.startswith("rare") for doc_id, _ in top))

        start = time.perf_counter()
        for i in range(500):
            lib.add("extra%04d" % i, "gateway 支付超时")
        add_elapsed = time.perf_counter() - start
        start = time.perf_counter()
        for i in range(500):
            lib.remove("extra%04d" % i)
        remove_elapsed = time.perf_counter() - start
        self.assertLess(add_elapsed / 500, 0.005)
        self.assertLess(remove_elapsed / 500, 0.005)

        for i in range(25):
            lib.remove("rare%02d" % i)
        top = index.search("timeout xylophone", 20)
        self.assertTrue(all(not doc_id.startswith("rare") for doc_id, _ in top))


if __name__ == "__main__":
    unittest.main()
