"""BM25Index 的行为与性能测试，暴力打分对拍。"""

import math
import random
import time
import unittest
from collections import Counter

from docbase import BM25Index, DocLibrary, rank_tokens


def brute_force(docs, query, k, k1=1.5, b=0.75):
    """参照实现：全量打分，按 (-score, doc_id) 取前 k。"""
    qterms = []
    seen = set()
    for word in rank_tokens(query):
        if word not in seen:
            seen.add(word)
            qterms.append(word)
    n = len(docs)
    if not qterms or n == 0 or k <= 0:
        return []
    tokenized = {doc_id: rank_tokens(text) for doc_id, text in docs.items()}
    df = Counter()
    for words in tokenized.values():
        df.update(set(words))
    avgdl = sum(len(words) for words in tokenized.values()) / n
    scored = []
    for doc_id, words in tokenized.items():
        tf = Counter(words)
        norm_base = k1 * (1.0 - b + b * len(words) / avgdl)
        score = 0.0
        for term in qterms:
            if term in tf:
                idf = math.log((n - df[term] + 0.5) / (df[term] + 0.5) + 1.0)
                score += idf * (tf[term] * (k1 + 1.0)) / (tf[term] + norm_base)
        if score > 0.0:
            scored.append((doc_id, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored[:k]


def assert_same_ranking(test_case, expected, actual):
    test_case.assertEqual([doc_id for doc_id, _ in expected],
                          [doc_id for doc_id, _ in actual])
    for (_, exp_score), (_, act_score) in zip(expected, actual):
        test_case.assertTrue(
            math.isclose(exp_score, act_score, rel_tol=1e-12, abs_tol=1e-12),
            "{} != {}".format(exp_score, act_score),
        )


class RankTokensTest(unittest.TestCase):
    def test_cjk_bigrams(self):
        self.assertEqual(rank_tokens("支付超时"), ["支付", "付超", "超时"])

    def test_single_cjk_char_kept(self):
        self.assertEqual(rank_tokens("亏"), ["亏"])
        self.assertEqual(rank_tokens("我，们"), ["我", "们"])

    def test_latin_and_digits(self):
        self.assertEqual(rank_tokens("Export Timeout-3"), ["export", "timeout", "3"])

    def test_mixed(self):
        self.assertEqual(
            rank_tokens("重启 gateway 服务"),
            ["重启", "gateway", "服务"],
        )


class BM25BasicTest(unittest.TestCase):
    def setUp(self):
        self.lib = DocLibrary()
        self.index = BM25Index(self.lib)

    def test_scores_match_hand_formula(self):
        self.lib.add("d1", "支付超时")
        self.lib.add("d2", "支付")
        self.lib.add("d3", "timeout")
        n = 3
        avgdl = 5.0 / 3.0
        idf = math.log((n - 2 + 0.5) / (2 + 0.5) + 1.0)
        exp_d1 = idf * 2.5 / (1.0 + 1.5 * (0.25 + 0.75 * 3.0 / avgdl))
        exp_d2 = idf * 2.5 / (1.0 + 1.5 * (0.25 + 0.75 * 1.0 / avgdl))
        result = self.index.search("支付", 3)
        self.assertEqual([doc_id for doc_id, _ in result], ["d2", "d1"])
        self.assertTrue(math.isclose(result[0][1], exp_d2))
        self.assertTrue(math.isclose(result[1][1], exp_d1))

    def test_tie_breaks_by_doc_id(self):
        self.lib.add("b2", "支付超时")
        self.lib.add("a1", "支付超时")
        self.lib.add("c3", "支付超时")
        result = self.index.search("支付", 2)
        self.assertEqual([doc_id for doc_id, _ in result], ["a1", "b2"])
        self.assertEqual(result[0][1], result[1][1])

    def test_query_terms_deduplicated(self):
        self.lib.add("d1", "gateway timeout")
        self.lib.add("d2", "gateway gateway gateway")
        single = self.index.search("gateway", 2)
        double = self.index.search("gateway gateway", 2)
        self.assertEqual(single, double)

    def test_empty_query_and_bad_k(self):
        self.lib.add("d1", "abc")
        self.assertEqual(self.index.search("", 5), [])
        self.assertEqual(self.index.search("  ，。", 5), [])
        self.assertEqual(self.index.search("abc", 0), [])
        self.assertEqual(self.index.search("abc", -1), [])

    def test_unknown_terms_ignored(self):
        self.lib.add("d1", "gateway")
        self.assertEqual(self.index.search("不存在的词", 5), [])
        expected = self.index.search("gateway", 5)
        self.assertEqual(self.index.search("gateway 不存在", 5), expected)

    def test_constructor_ingests_existing_library(self):
        self.lib.add("d1", "支付超时排查")
        self.lib.add("d2", "回调丢失")
        index = BM25Index(self.lib)
        self.assertEqual(index.stats()["docs"], 2)
        self.assertEqual([doc_id for doc_id, _ in index.search("支付", 5)], ["d1"])

    def test_k_larger_than_hits(self):
        self.lib.add("d1", "abc")
        self.lib.add("d2", "abc def")
        result = self.index.search("abc", 10)
        self.assertEqual(len(result), 2)

    def test_stats_counters(self):
        self.lib.add("d1", "abc")
        self.index.search("abc", 1)
        self.index.search("zzz", 1)
        stats = self.index.stats()
        self.assertEqual(stats["docs"], 1)
        self.assertEqual(stats["searches"], 2)
        self.assertEqual(stats["scored"], 1)


class BM25SyncTest(unittest.TestCase):
    def test_remove_hides_doc_and_updates_stats(self):
        lib = DocLibrary()
        lib.add("d1", "支付超时")
        lib.add("d2", "支付回调")
        index = BM25Index(lib)
        self.assertEqual(len(index.search("支付", 5)), 2)
        lib.remove("d1")
        self.assertEqual([doc_id for doc_id, _ in index.search("支付", 5)], ["d2"])
        self.assertEqual(index.stats()["docs"], 1)
        self.assertEqual(index.search("超时", 5), [])

    def test_readd_recomputes_with_new_text(self):
        lib = DocLibrary()
        lib.add("d1", "支付超时")
        index = BM25Index(lib)
        self.assertEqual(len(index.search("超时", 5)), 1)
        lib.add("d1", "回调丢失")
        self.assertEqual(index.search("超时", 5), [])
        self.assertEqual([doc_id for doc_id, _ in index.search("回调", 5)], ["d1"])
        self.assertEqual(index.stats()["docs"], 1)

    def test_remove_missing_is_noop(self):
        lib = DocLibrary()
        lib.add("d1", "abc")
        index = BM25Index(lib)
        self.assertFalse(lib.remove("nope"))
        self.assertEqual(index.stats()["docs"], 1)

    def test_avgdl_follows_mutation(self):
        lib = DocLibrary()
        lib.add("d1", "支付")
        lib.add("d2", "支付超时排查步骤")
        index = BM25Index(lib)
        before = index.search("支付", 5)
        lib.remove("d2")
        after = index.search("支付", 5)
        self.assertEqual([doc_id for doc_id, _ in after], ["d1"])
        self.assertNotEqual(before[0][1], after[0][1])


class BM25BruteForceTest(unittest.TestCase):
    def _random_doc(self, rng, cjk_pool, latin_pool):
        parts = []
        for _ in range(rng.randint(2, 8)):
            if rng.random() < 0.5:
                parts.append("".join(rng.choice(cjk_pool)
                                     for _ in range(rng.randint(1, 4))))
            else:
                parts.append(rng.choice(latin_pool))
        return " ".join(parts)

    def _random_query(self, rng, cjk_pool, latin_pool):
        parts = []
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.5:
                parts.append("".join(rng.choice(cjk_pool)
                                     for _ in range(rng.randint(1, 3))))
            else:
                parts.append(rng.choice(latin_pool))
        return " ".join(parts)

    def test_random_corpus_matches_brute_force(self):
        rng = random.Random(20260922)
        cjk_pool = [chr(0x4E00 + i) for i in range(120)]
        latin_pool = ["w%d" % i for i in range(200)]
        lib = DocLibrary()
        docs = {}
        for i in range(400):
            text = self._random_doc(rng, cjk_pool, latin_pool)
            if i % 17 == 0 and docs:
                text = docs["d%04d" % (i - 1)]  # 制造同分文档
            doc_id = "d%04d" % i
            lib.add(doc_id, text)
            docs[doc_id] = text
        index = BM25Index(lib)

        def check_all():
            for _ in range(30):
                query = self._random_query(rng, cjk_pool, latin_pool)
                k = rng.choice([1, 3, 5, 10, 20])
                assert_same_ranking(
                    self, brute_force(docs, query, k), index.search(query, k)
                )

        check_all()

        # 删一半再混跑：随机增删改后继续对拍，不许有幽灵分数。
        ids = sorted(docs)
        rng.shuffle(ids)
        for doc_id in ids[: len(ids) // 2]:
            self.assertTrue(lib.remove(doc_id))
            del docs[doc_id]
        for round_no in range(60):
            op = rng.random()
            if op < 0.4:
                doc_id = "m%04d" % round_no
                text = self._random_doc(rng, cjk_pool, latin_pool)
                lib.add(doc_id, text)
                docs[doc_id] = text
            elif op < 0.7 and docs:
                doc_id = rng.choice(sorted(docs))
                self.assertTrue(lib.remove(doc_id))
                del docs[doc_id]
            elif docs:
                doc_id = rng.choice(sorted(docs))
                text = self._random_doc(rng, cjk_pool, latin_pool)
                lib.add(doc_id, text)
                docs[doc_id] = text
            check_all()
            for doc_id, _ in index.search(
                self._random_query(rng, cjk_pool, latin_pool), 50
            ):
                self.assertIn(doc_id, docs)


class BM25PerfTest(unittest.TestCase):
    def test_common_plus_rare_top20(self):
        rng = random.Random(7)
        vocab = ["w%d" % i for i in range(10000)]
        lib = DocLibrary()
        index = BM25Index(lib)
        hits = 0
        for i in range(100000):
            words = [rng.choice(vocab) for _ in range(6)]
            has_common = rng.random() < 0.5
            has_rare = rng.random() < 0.005
            if has_common:
                words.append("common")
            if has_rare:
                words.append("rare")
            if has_common or has_rare:
                hits += 1
            lib.add("d%06d" % i, " ".join(words))

        start = time.perf_counter()
        result = index.search("common rare", 20)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(result), 20)
        self.assertLess(elapsed, 1.0)
        scored = index.stats()["scored"]
        self.assertLessEqual(scored, hits * 0.3)

        # 单篇增删开销不随库涨：十万篇上再做两千次增删应瞬间完成。
        start = time.perf_counter()
        for j in range(2000):
            lib.add("extra%d" % j, "hello world")
            lib.remove("extra%d" % j)
        self.assertLess(time.perf_counter() - start, 1.0)
        self.assertEqual(index.stats()["docs"], 100000)


if __name__ == "__main__":
    unittest.main()
