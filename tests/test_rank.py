"""BM25Index 的行为与性能测试。"""

import math
import random
import time
import unittest
from collections import Counter

from docbase import BM25Index, DocLibrary
from docbase.rank import rank_tokens


def brute_force(lib, query, k, k1=1.5, b=0.75):
    """独立实现的暴力打分：给每篇候选文档算 BM25，取前 k。"""
    words = list(dict.fromkeys(rank_tokens(query)))
    docs = lib.scan()
    n_docs = len(docs)
    if not words or n_docs == 0 or k <= 0:
        return []
    counts = {doc_id: Counter(rank_tokens(text)) for doc_id, text in docs}
    avg = sum(sum(c.values()) for c in counts.values()) / n_docs
    df = Counter()
    for c in counts.values():
        for word in c:
            df[word] += 1
    hits = []
    for doc_id, c in counts.items():
        dl = sum(c.values())
        norm = k1 * (1.0 - b + b * dl / avg)
        score = 0.0
        matched = False
        for word in words:
            tf = c.get(word)
            if tf:
                matched = True
                idf = math.log((n_docs - df[word] + 0.5) / (df[word] + 0.5) + 1.0)
                score += idf * tf * (k1 + 1.0) / (tf + norm)
        if matched:
            hits.append((doc_id, score))
    hits.sort(key=lambda e: (-e[1], e[0]))
    return hits[:k]


def assert_same_ranking(test_case, expected, actual):
    test_case.assertEqual([doc_id for doc_id, _ in expected],
                          [doc_id for doc_id, _ in actual])
    for (_, e_score), (_, a_score) in zip(expected, actual):
        test_case.assertAlmostEqual(e_score, a_score, places=9)


class RankTokensTest(unittest.TestCase):
    def test_cjk_bigrams(self):
        self.assertEqual(rank_tokens("支付超时"), ["支付", "付超", "超时"])

    def test_single_cjk_char_kept(self):
        self.assertEqual(rank_tokens("支"), ["支"])
        self.assertEqual(rank_tokens("支。"), ["支"])

    def test_punctuation_breaks_segments(self):
        self.assertEqual(rank_tokens("苹果，香蕉"), ["苹果", "香蕉"])

    def test_latin_and_digits(self):
        self.assertEqual(rank_tokens("Export Timeout-3"), ["export", "timeout", "3"])

    def test_mixed(self):
        self.assertEqual(
            rank_tokens("重启 gateway 服务"),
            ["重启", "gateway", "服务"],
        )

    def test_empty(self):
        self.assertEqual(rank_tokens(""), [])
        self.assertEqual(rank_tokens("  ，。！ "), [])


class BM25IndexTest(unittest.TestCase):
    def setUp(self):
        self.lib = DocLibrary()

    def test_defaults(self):
        index = BM25Index(self.lib)
        self.assertEqual(index.k1, 1.5)
        self.assertEqual(index.b, 0.75)

    def test_constructor_ingests_existing_docs(self):
        self.lib.add("d1", "支付超时排查")
        self.lib.add("d2", "gateway timeout")
        index = BM25Index(self.lib)
        self.assertEqual(index.stats()["docs"], 2)
        self.assertEqual([doc_id for doc_id, _ in index.search("支付", 10)], ["d1"])

    def test_follows_add_replace_remove(self):
        index = BM25Index(self.lib)
        self.lib.add("d1", "支付超时")
        self.lib.add("d2", "回调丢失")
        self.assertEqual([i for i, _ in index.search("支付", 10)], ["d1"])
        self.lib.add("d1", "回调重试")
        self.assertEqual(index.search("支付", 10), [])
        self.assertEqual([i for i, _ in index.search("回调", 10)], ["d1", "d2"])
        self.lib.remove("d2")
        self.assertEqual([i for i, _ in index.search("回调", 10)], ["d1"])
        self.assertEqual(index.stats()["docs"], 1)

    def test_removed_docs_never_surface(self):
        self.lib.add("d1", "支付超时")
        self.lib.add("d2", "支付回调")
        index = BM25Index(self.lib)
        self.lib.remove("d1")
        results = index.search("支付", 10)
        self.assertEqual([i for i, _ in results], ["d2"])
        self.lib.remove("d2")
        self.assertEqual(index.search("支付", 10), [])

    def test_readd_recomputes_with_new_text(self):
        self.lib.add("d1", "支付超时")
        index = BM25Index(self.lib)
        self.lib.remove("d1")
        self.lib.add("d1", "网关日志")
        self.assertEqual(index.search("支付", 10), [])
        self.assertEqual([i for i, _ in index.search("网关", 10)], ["d1"])

    def test_tie_breaks_by_doc_id(self):
        self.lib.add("b", "支付超时")
        self.lib.add("a", "支付超时")
        self.lib.add("c", "支付超时")
        index = BM25Index(self.lib)
        self.assertEqual([i for i, _ in index.search("支付", 10)], ["a", "b", "c"])
        self.assertEqual([i for i, _ in index.search("支付", 1)], ["a"])

    def test_top_k_limits_results(self):
        for i in range(5):
            self.lib.add("d%d" % i, "支付超时 " + "日志 " * i)
        index = BM25Index(self.lib)
        self.assertEqual(len(index.search("支付", 3)), 3)
        self.assertEqual(len(index.search("支付", 10)), 5)

    def test_score_matches_hand_computation(self):
        self.lib.add("d1", "支付超时")
        self.lib.add("d2", "支付回调丢失")
        index = BM25Index(self.lib)
        n_docs, df = 2, 2
        idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
        avg = (3 + 5) / 2  # 支付超时 -> 3 个二字组，支付回调丢失 -> 5 个
        norm = 1.5 * (1.0 - 0.75 + 0.75 * 3 / avg)
        expected = idf * 1 * 2.5 / (1 + norm)
        results = dict(index.search("支付", 10))
        self.assertEqual(set(results), {"d1", "d2"})
        self.assertAlmostEqual(results["d1"], expected, places=12)
        self.assertGreater(results["d1"], results["d2"])  # 短文档分更高

    def test_query_terms_deduplicated(self):
        self.lib.add("d1", "支付超时")
        index = BM25Index(self.lib)
        single = index.search("支付", 10)
        repeated = index.search("支付 支付 支付", 10)
        self.assertEqual([i for i, _ in single], [i for i, _ in repeated])
        self.assertAlmostEqual(single[0][1], repeated[0][1], places=12)

    def test_empty_query_and_zero_k(self):
        self.lib.add("d1", "支付超时")
        index = BM25Index(self.lib)
        self.assertEqual(index.search("", 10), [])
        self.assertEqual(index.search("  ，。 ", 10), [])
        self.assertEqual(index.search("支付", 0), [])
        self.assertEqual(index.search("没出现过的词", 10), [])

    def test_empty_library(self):
        index = BM25Index(self.lib)
        self.assertEqual(index.search("支付", 10), [])
        self.assertEqual(index.stats()["avg_len"], 0.0)

    def test_custom_k1_b(self):
        self.lib.add("d1", "支付 支付 超时")
        self.lib.add("d2", "支付")
        for k1, b in ((1.2, 0.5), (2.0, 1.0)):
            index = BM25Index(self.lib, k1=k1, b=b)
            assert_same_ranking(self, brute_force(self.lib, "支付", 5, k1, b),
                                index.search("支付", 5))

    def test_stats_counters(self):
        self.lib.add("d1", "支付超时")
        index = BM25Index(self.lib)
        index.search("支付", 10)
        index.search("支付", 10)
        stats = index.stats()
        self.assertEqual(stats["docs"], 1)
        self.assertEqual(stats["searches"], 2)
        self.assertEqual(stats["scored"], 2)
        self.assertGreater(stats["terms"], 0)
        self.assertGreater(stats["avg_len"], 0.0)


class BruteForceCrossCheckTest(unittest.TestCase):
    """随机语料与查询下，名次与分数同暴力打分对拍。"""

    def setUp(self):
        rng = random.Random(20260922)
        chars = "支付超时回调丢失网关日志重试排查告警熔断限流"
        self.vocab = (
            ["".join(rng.choice(chars) for _ in range(2)) for _ in range(60)]
            + ["w%03d" % i for i in range(40)]
        )
        self.rng = random.Random(7)
        self.lib = DocLibrary()
        for i in range(300):
            self.lib.add("doc-%03d" % i, self._random_text())
        self.index = BM25Index(self.lib)

    def _random_text(self):
        rng = self.rng
        return " ".join(
            rng.choice(self.vocab) for _ in range(rng.randint(3, 12))
        )

    def _random_query(self):
        rng = self.rng
        return " ".join(rng.choice(self.vocab) for _ in range(rng.randint(1, 3)))

    def test_random_queries_match_brute_force(self):
        for _ in range(30):
            query = self._random_query()
            k = self.rng.choice([1, 3, 10, 50])
            assert_same_ranking(self, brute_force(self.lib, query, k),
                                self.index.search(query, k))

    def test_remove_half_then_mixed_ops_no_ghosts(self):
        rng = random.Random(99)
        ids = self.lib.ids()
        removed = set(rng.sample(ids, len(ids) // 2))
        for doc_id in removed:
            self.lib.remove(doc_id)
        # 混合跑：新增、覆盖、删除、删不存在的主键。
        for i in range(60):
            self.lib.add("new-%03d" % i, self._random_text())
        for doc_id in rng.sample(self.lib.ids(), 40):
            self.lib.add(doc_id, self._random_text())
        for doc_id in rng.sample(self.lib.ids(), 30):
            self.lib.remove(doc_id)
        self.assertFalse(self.lib.remove("never-existed"))

        for _ in range(30):
            query = self._random_query()
            expected = brute_force(self.lib, query, 10)
            actual = self.index.search(query, 10)
            assert_same_ranking(self, expected, actual)
            for doc_id, score in actual:
                self.assertNotIn(doc_id, removed)
                self.assertIsNotNone(self.lib.get(doc_id))
                self.assertGreater(score, 0.0)


class PerformanceTest(unittest.TestCase):
    """十万篇、万级词表：常见词配生僻词查前二十。"""

    @classmethod
    def setUpClass(cls):
        rng = random.Random(154)
        chars = "支付超时回调丢失网关日志重试排查告警熔断限流缓存队列"
        cls.vocab = (
            ["".join(rng.choice(chars) for _ in range(2)) for _ in range(5000)]
            + ["w%04d" % i for i in range(5000)]
        )
        cls.lib = DocLibrary()
        cls.common_ids = set()
        cls.rare_ids = set()
        for i in range(100000):
            doc_id = "t%06d" % i
            words = [rng.choice(cls.vocab) for _ in range(rng.randint(6, 12))]
            if rng.random() < 0.4:
                words.append("commonword")
                cls.common_ids.add(doc_id)
            if rng.random() < 0.001:
                words.append("rareword")
                cls.rare_ids.add(doc_id)
            cls.lib.add(doc_id, " ".join(words))
        cls.index = BM25Index(cls.lib)

    def test_top20_under_a_second_and_scored_bounded(self):
        hits = len(self.common_ids | self.rare_ids)
        before = self.index.stats()["scored"]
        start = time.perf_counter()
        results = self.index.search("commonword rareword", 20)
        elapsed = time.perf_counter() - start
        scored = self.index.stats()["scored"] - before

        self.assertEqual(len(results), 20)
        self.assertLess(elapsed, 1.0)
        self.assertLessEqual(scored, hits * 0.3)
        assert_same_ranking(
            self, brute_force(self.lib, "commonword rareword", 20), results)

    def test_single_doc_add_remove_cost_does_not_grow(self):
        start = time.perf_counter()
        for i in range(500):
            self.lib.add("tmp-%d" % i, "支付超时 网关日志")
            self.lib.remove("tmp-%d" % i)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0)
        self.assertEqual(self.index.stats()["docs"], 100000)


if __name__ == "__main__":
    unittest.main()
