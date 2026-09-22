"""BM25Index 的行为与性能测试，不动 test_library / test_text 基线。"""

import math
import random
import time
import unittest
from collections import Counter

from docbase.library import DocLibrary
from docbase.rank import BM25Index, rank_tokens


def brute_force(lib, query, k, k1=1.5, b=0.75):
    """暴力打分：全库重算 df / 平均长度，每个候选都算一遍分。"""
    counters = {doc_id: Counter(rank_tokens(text)) for doc_id, text in lib.scan()}
    n = len(counters)
    qterms = list(dict.fromkeys(rank_tokens(query)))
    if not qterms or n == 0 or k <= 0:
        return []
    total = sum(sum(c.values()) for c in counters.values())
    avgdl = total / n
    dfs = {}
    for term in qterms:
        dfs[term] = sum(1 for c in counters.values() if term in c)
    scored = []
    for doc_id, counter in counters.items():
        dl = sum(counter.values())
        norm = k1 * (1.0 - b + b * dl / avgdl)
        score = 0.0
        for term in qterms:
            tf = counter.get(term)
            if tf:
                df = dfs[term]
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
                score += idf * tf * (k1 + 1.0) / (tf + norm)
        if score > 0.0:
            scored.append((doc_id, score))
    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    return scored[:k]


def assert_ranking_equal(testcase, got, want):
    testcase.assertEqual([doc_id for doc_id, _ in got], [doc_id for doc_id, _ in want])
    for (_, g), (_, w) in zip(got, want):
        testcase.assertAlmostEqual(g, w, places=9)


class RankTokensTest(unittest.TestCase):
    def test_cjk_segment_becomes_bigrams(self):
        self.assertEqual(rank_tokens("支付超时"), ["支付", "付超", "超时"])

    def test_lone_cjk_char_kept(self):
        self.assertEqual(rank_tokens("我"), ["我"])
        self.assertEqual(rank_tokens("重启，服务"), ["重启", "服务"])

    def test_latin_like_tokens(self):
        self.assertEqual(rank_tokens("Export Timeout-3"), ["export", "timeout", "3"])

    def test_mixed_text(self):
        self.assertEqual(rank_tokens("重启 gateway 服务"), ["重启", "gateway", "服务"])

    def test_empty(self):
        self.assertEqual(rank_tokens(""), [])
        self.assertEqual(rank_tokens("  ，。！ "), [])


class BM25BasicTest(unittest.TestCase):
    def setUp(self):
        self.lib = DocLibrary()
        self.index = BM25Index(self.lib)

    def test_ranks_relevant_doc_first(self):
        self.lib.add("a", "支付超时排查 支付超时")
        self.lib.add("b", "支付回调丢失")
        self.lib.add("c", "网关日志")
        got = self.index.search("支付超时", 3)
        self.assertEqual([doc_id for doc_id, _ in got], ["a", "b"])
        self.assertGreater(got[0][1], got[1][1])

    def test_tie_breaks_by_doc_id(self):
        self.lib.add("b", "网关 超时")
        self.lib.add("a", "网关 超时")
        got = self.index.search("网关", 5)
        self.assertEqual([doc_id for doc_id, _ in got], ["a", "b"])
        self.assertEqual(got[0][1], got[1][1])

    def test_constructor_sees_existing_docs(self):
        self.lib.add("a", "timeout")
        index = BM25Index(self.lib)
        self.assertEqual([doc_id for doc_id, _ in index.search("timeout", 5)], ["a"])
        index.close()

    def test_k_limits_results(self):
        for i in range(5):
            self.lib.add("d%d" % i, "网关")
        self.assertEqual(len(self.index.search("网关", 3)), 3)
        self.assertEqual(len(self.index.search("网关", 99)), 5)

    def test_empty_query_and_zero_k(self):
        self.lib.add("a", "网关")
        self.assertEqual(self.index.search("", 3), [])
        self.assertEqual(self.index.search("  ，。", 3), [])
        self.assertEqual(self.index.search("网关", 0), [])

    def test_empty_library(self):
        self.assertEqual(self.index.search("网关", 3), [])

    def test_remove_hides_doc_and_readd_recomputes(self):
        self.lib.add("a", "支付 支付 支付")
        self.lib.add("b", "支付")
        top_before = self.index.search("支付", 2)[0][0]
        self.assertEqual(top_before, "a")
        self.lib.remove("a")
        got = self.index.search("支付", 2)
        self.assertEqual([doc_id for doc_id, _ in got], ["b"])
        self.lib.add("a", "网关")
        got = self.index.search("支付", 2)
        self.assertEqual([doc_id for doc_id, _ in got], ["b"])
        self.assertEqual(self.index.search("网关", 2)[0][0], "a")

    def test_overwrite_updates_index(self):
        self.lib.add("a", "支付")
        self.assertEqual(len(self.index.search("支付", 5)), 1)
        self.lib.add("a", "网关")
        self.assertEqual(self.index.search("支付", 5), [])
        self.assertEqual(self.index.search("网关", 5)[0][0], "a")

    def test_close_stops_sync(self):
        self.lib.add("a", "支付")
        self.index.close()
        self.lib.add("b", "支付")
        self.assertEqual([doc_id for doc_id, _ in self.index.search("支付", 5)], ["a"])

    def test_stats_counters(self):
        self.lib.add("a", "支付 网关")
        self.lib.add("b", "支付")
        before = self.index.stats()
        self.assertEqual(before["docs"], 2)
        self.assertEqual(before["scored"], 0)
        self.index.search("支付", 5)
        after = self.index.stats()
        self.assertEqual(after["searches"], before["searches"] + 1)
        self.assertEqual(after["candidates"], before["candidates"] + 2)
        self.assertGreater(after["scored"], before["scored"])
        self.assertGreater(after["avgdl"], 0.0)


class BM25BruteForceTest(unittest.TestCase):
    """随机语料随机查询，跟暴力打分对拍到浮点误差。"""

    CJK = "支付超时排查网关回调丢失重启服务日志告警工单"
    LATIN = ["timeout", "retry", "export", "gateway", "log", "error", "warn", "ok"]

    def rand_text(self, rng):
        parts = []
        for _ in range(rng.randrange(1, 7)):
            if rng.random() < 0.5:
                parts.append(
                    "".join(rng.choice(self.CJK) for _ in range(rng.randrange(1, 6)))
                )
            else:
                parts.append(rng.choice(self.LATIN))
        sep = " " if rng.random() < 0.8 else "，"
        return sep.join(parts)

    def rand_query(self, rng):
        if rng.random() < 0.3:
            return "".join(rng.choice(self.CJK) for _ in range(rng.randrange(1, 4)))
        return " ".join(rng.choice(self.LATIN) for _ in range(rng.randrange(1, 3)))

    def check_all(self, lib, index, rng):
        queries = [self.rand_query(rng) for _ in range(15)]
        queries += ["", "  ，。", "支付", "timeout gateway", "不存在的词"]
        for query in queries:
            for k in (1, 3, 10, 1000):
                got = index.search(query, k)
                want = brute_force(lib, query, k)
                assert_ranking_equal(self, got, want)
                for doc_id, _ in got:
                    self.assertIsNotNone(lib.get(doc_id))  # 不许有幽灵分数

    def test_randomized_mixed_ops_match_brute_force(self):
        rng = random.Random(20260922)
        lib = DocLibrary()
        index = BM25Index(lib)
        live = []
        for round_no in range(6):
            if round_no == 3 and live:
                # 删一半，再接着混跑
                for doc_id in rng.sample(live, len(live) // 2):
                    self.assertTrue(lib.remove(doc_id))
                    live.remove(doc_id)
            for _ in range(60):
                roll = rng.random()
                if roll < 0.5 or not live:
                    doc_id = "d%04d" % rng.randrange(400)
                    if lib.add(doc_id, self.rand_text(rng)):
                        live.append(doc_id)
                elif roll < 0.8:
                    lib.add(rng.choice(live), self.rand_text(rng))
                else:
                    victim = rng.choice(live)
                    self.assertTrue(lib.remove(victim))
                    live.remove(victim)
            self.check_all(lib, index, rng)
        stats = index.stats()
        self.assertEqual(stats["docs"], lib.count())
        self.assertLessEqual(stats["scored"], stats["candidates"])


class BM25PerfTest(unittest.TestCase):
    """十万篇、万级词表：常见词配生僻词查前二十。"""

    DOCS = 100000
    VOCAB = 10000

    def test_common_plus_rare_top20(self):
        rng = random.Random(154)
        vocab = ["w%05d" % i for i in range(self.VOCAB)]
        lib = DocLibrary()
        index = BM25Index(lib)
        for i in range(self.DOCS):
            words = [vocab[rng.randrange(self.VOCAB)] for _ in range(8)]
            if i % 2 == 0:
                words.append("commonword")
            if i % 1500 == 0:
                words.append("rareword")
            lib.add("d%06d" % i, " ".join(words))
        self.assertEqual(index.stats()["docs"], self.DOCS)

        before = index.stats()
        start = time.perf_counter()
        got = index.search("commonword rareword", 20)
        elapsed = time.perf_counter() - start
        after = index.stats()
        self.assertEqual(len(got), 20)
        self.assertLess(elapsed, 1.0)
        hits = after["candidates"] - before["candidates"]
        scored = after["scored"] - before["scored"]
        self.assertGreater(hits, 40000)  # 常见词命中大半库
        self.assertLessEqual(scored, hits * 0.3)

        # 单篇增删开销不随库涨：十万篇的库上反复增删，均值仍是微秒级
        start = time.perf_counter()
        for i in range(2000):
            lib.add("tmp-churn", "临时 文档 churn %d" % i)
            lib.remove("tmp-churn")
        per_op = (time.perf_counter() - start) / 2000
        self.assertLess(per_op, 0.002)

        # 搅动之后排序结果不变，也没有幽灵分数
        again = index.search("commonword rareword", 20)
        assert_ranking_equal(self, again, got)
        self.assertNotIn("tmp-churn", [doc_id for doc_id, _ in again])


if __name__ == "__main__":
    unittest.main()
