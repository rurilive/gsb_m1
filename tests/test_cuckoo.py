"""CuckooFilter 与 DedupStore 布谷鸟后端的新行为测试。"""

import random
import time
import unittest

from crawlkit import CuckooFilter, DedupStore, NotSupportedError
from crawlkit.hashing import fingerprint, hash_pair


def same_fp_keys(cf, fp_bits, count=2):
    """找 count 个指纹相同但候选桶互不相交的键。"""
    keys = []
    i = 0
    while len(keys) < count:
        k = "fp-key-%d" % i
        i += 1
        h1, h2 = hash_pair(k)
        fp = fingerprint(h2, fp_bits)
        if keys and fingerprint(hash_pair(keys[0])[1], fp_bits) != fp:
            continue
        cand = set(cf._candidates(h1, fp, cf.num_buckets))
        if any(
            cand & set(cf._candidates(hash_pair(p)[0], fp, cf.num_buckets))
            for p in keys
        ):
            continue
        keys.append(k)
    return keys


class TestCuckooFilter(unittest.TestCase):
    def test_added_keys_always_hit(self):
        cf = CuckooFilter(capacity=1000, fp_bits=12)
        keys = ["u%d" % i for i in range(1000)]
        for k in keys:
            cf.add(k)
        for k in keys:
            self.assertIn(k, cf)

    def test_remove_basic(self):
        cf = CuckooFilter(capacity=100, fp_bits=12)
        for i in range(50):
            cf.add("u%d" % i)
        self.assertTrue(cf.remove("u7"))
        self.assertNotIn("u7", cf)
        for i in range(50):
            if i != 7:
                self.assertIn("u%d" % i, cf)

    def test_remove_missing_returns_false(self):
        cf = CuckooFilter(capacity=10, fp_bits=12)
        cf.add("a")
        self.assertFalse(cf.remove("never-added"))
        self.assertIn("a", cf)
        self.assertEqual(len(cf), 1)

    def test_same_fingerprint_keys_independent(self):
        cf = CuckooFilter(capacity=100, fp_bits=8)
        k1, k2 = same_fp_keys(cf, 8)
        cf.add(k1)
        cf.add(k2)
        cf.remove(k1)
        self.assertNotIn(k1, cf)
        self.assertIn(k2, cf)

    def test_add_idempotent_and_len(self):
        cf = CuckooFilter(capacity=10, fp_bits=12)
        cf.add("a")
        cf.add("a")
        self.assertEqual(len(cf), 1)
        cf.remove("a")
        self.assertEqual(len(cf), 0)
        self.assertNotIn("a", cf)

    def test_growth_keeps_every_hit(self):
        cf = CuckooFilter(capacity=8, fp_bits=12)
        before = cf.num_buckets
        keys = ["grow-%d" % i for i in range(500)]
        for k in keys:
            cf.add(k)
        self.assertGreater(cf.num_buckets, before)
        for k in keys:
            self.assertIn(k, cf)

    def test_long_kick_chains_no_recursion(self):
        # 小桶数加小指纹硬造长踢出链，递归实现早炸了
        cf = CuckooFilter(capacity=4, fp_bits=4)
        keys = ["chain-%d" % i for i in range(300)]
        for k in keys:
            cf.add(k)
        for k in keys:
            self.assertIn(k, cf)

    def test_false_positive_rate_12bit(self):
        rng = random.Random(20260922)
        cf = CuckooFilter(capacity=100000, fp_bits=12)
        inside = set()
        while len(inside) < 100000:
            inside.add(rng.getrandbits(64))
        for k in inside:
            cf.add(k)
        probes = 0
        hits = 0
        while probes < 100000:
            q = rng.getrandbits(64)
            if q in inside:
                continue
            probes += 1
            if q in cf:
                hits += 1
        self.assertLessEqual(hits / probes, 0.002)

    def test_stress_against_plain_set(self):
        rng = random.Random(147)
        cf = CuckooFilter(capacity=20000, fp_bits=16)
        live = set()
        for _ in range(30000):
            op = rng.random()
            if op < 0.5 or not live:
                k = "k-%d" % rng.getrandbits(40)
                cf.add(k)
                live.add(k)
            elif op < 0.75:
                k = rng.choice(tuple(live))
                cf.remove(k)
                live.discard(k)
            else:
                k = "k-%d" % rng.getrandbits(40)
                if k in live:
                    self.assertIn(k, cf)
        for k in live:
            self.assertIn(k, cf)

    def test_mixed_ops_under_six_seconds(self):
        cf = CuckooFilter(capacity=100000, fp_bits=12)
        keys = ["perf-%d" % i for i in range(40000)]
        start = time.monotonic()
        ops = 0
        for k in keys:
            cf.add(k)
            ops += 1
        for i, k in enumerate(keys):
            if i % 2 == 0:
                cf.remove(k)
            else:
                self.assertIn(k, cf)
            ops += 1
        for i in range(20000):
            "q-%d" % i in cf
            ops += 1
        self.assertEqual(ops, 100000)
        self.assertLess(time.monotonic() - start, 6.0)

    def test_high_load_keeps_hits(self):
        cf = CuckooFilter(capacity=10000, fp_bits=12)
        keys = ["load-%d" % i for i in range(9500)]
        for k in keys:
            cf.add(k)
        for k in keys:
            self.assertIn(k, cf)

    def test_round_trip_byte_identical(self):
        cf = CuckooFilter(capacity=500, fp_bits=12)
        for i in range(300):
            cf.add("k%d" % i)
        for i in range(0, 300, 3):
            cf.remove("k%d" % i)
        blob = cf.to_bytes()
        back = CuckooFilter.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(len(back), len(cf))
        for i in range(300):
            self.assertEqual("k%d" % i in back, "k%d" % i in cf)
        back.remove("k1")
        self.assertNotIn("k1", back)

    def test_stats_is_fresh_dict(self):
        cf = CuckooFilter(capacity=10, fp_bits=12)
        st = cf.stats()
        st["added"] = 99
        self.assertEqual(cf.stats()["added"], 0)

    def test_bad_args_rejected(self):
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=0)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=10, fp_bits=0)
        with self.assertRaises(ValueError):
            CuckooFilter(capacity=10, fp_bits=64)

    def test_bad_magic_rejected(self):
        blob = bytearray(CuckooFilter(capacity=10, fp_bits=12).to_bytes())
        blob[0:4] = b"NOPE"
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(bytes(blob))

    def test_truncated_rejected(self):
        blob = CuckooFilter(capacity=10, fp_bits=12).to_bytes()
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(b"DC")
        with self.assertRaises(ValueError):
            CuckooFilter.from_bytes(blob[:-1])


class TestDedupStoreCuckooBackend(unittest.TestCase):
    def test_retry_really_removes(self):
        s = DedupStore(capacity=100, backend="cuckoo")
        s.mark("u1")
        s.mark("u2")
        self.assertTrue(s.is_duplicate("u1"))
        self.assertTrue(s.retry("u1"))
        self.assertFalse(s.is_duplicate("u1"))
        self.assertTrue(s.is_duplicate("u2"))

    def test_retry_unknown_key(self):
        s = DedupStore(capacity=100, backend="cuckoo")
        self.assertFalse(s.retry("never-marked"))

    def test_bloom_backend_still_default(self):
        s = DedupStore(capacity=100)
        s.mark("u1")
        with self.assertRaises(NotSupportedError):
            s.retry("u1")

    def test_stats_reports_backend(self):
        s = DedupStore(capacity=100, backend="cuckoo")
        s.mark("u1")
        st = s.stats()
        self.assertEqual(st["backend"], "cuckoo")
        self.assertEqual(st["filter"]["added"], 1)
        s.retry("u1")
        self.assertEqual(s.stats()["filter"]["added"], 0)

    def test_round_trip_cuckoo_backend(self):
        s = DedupStore(capacity=200, fp_rate=0.01, backend="cuckoo")
        for i in range(20):
            s.mark("u%d" % i)
        s.retry("u3")
        blob = s.to_bytes()
        back = DedupStore.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(back.backend, "cuckoo")
        self.assertEqual(back.stats()["marks"], 20)
        self.assertFalse(back.is_duplicate("u3"))
        self.assertTrue(back.is_duplicate("u4"))
        back.retry("u4")
        self.assertFalse(back.is_duplicate("u4"))

    def test_bad_backend_rejected(self):
        with self.assertRaises(ValueError):
            DedupStore(capacity=10, backend="nope")


if __name__ == "__main__":
    unittest.main()
