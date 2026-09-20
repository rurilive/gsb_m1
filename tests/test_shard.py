"""ShardBloomFilter 新行为：在线添片、跨片查询、整体假阳性率、老格式读回、并发写。"""
import random
import threading
import unittest

from bloomx import BloomFilter, ShardBloomFilter, ShardCapacityError
from bloomx.shard import MAGIC


def _fill(sbf, start, count):
    for i in range(start, start + count):
        sbf.add("evt-%d" % i)


class TestOnlineAddShard(unittest.TestCase):
    def test_add_shard_grows_without_touching_old(self):
        sbf = ShardBloomFilter(capacity=1000, fp_rate=0.01)
        _fill(sbf, 0, 100)
        old = sbf.shards[0]
        old_bits = bytes(old._bits)

        self.assertEqual(sbf.add_shard(), 1)
        self.assertEqual(len(sbf.shards), 2)
        # 旧片原封不动
        self.assertIs(sbf.shards[0], old)
        self.assertEqual(bytes(sbf.shards[0]._bits), old_bits)

    def test_new_writes_land_in_new_shard(self):
        sbf = ShardBloomFilter(capacity=1000, fp_rate=0.01)
        sbf.add_shard()
        sbf.add("newbie")
        self.assertNotIn("newbie", sbf.shards[0])
        self.assertIn("newbie", sbf.shards[-1])

    def test_len_sums_all_shards(self):
        sbf = ShardBloomFilter(capacity=100, fp_rate=0.01)
        _fill(sbf, 0, 30)
        sbf.add_shard()
        _fill(sbf, 1000, 20)
        self.assertEqual(len(sbf), 50)


class TestCrossShardQuery(unittest.TestCase):
    def test_finds_items_regardless_of_shard(self):
        sbf = ShardBloomFilter(capacity=100, fp_rate=0.01)
        sbf.add("s0-item")
        sbf.add_shard()
        sbf.add("s1-item")
        sbf.add_shard()
        sbf.add("s2-item")
        for item in ("s0-item", "s1-item", "s2-item"):
            self.assertIn(item, sbf)

    def test_missing_any_shard_breaks_dedup(self):
        # 证明查询必须覆盖所有片：只查后两片时，落在首片的数据会漏判
        sbf = ShardBloomFilter(capacity=100, fp_rate=0.01)
        sbf.add("old-item")
        sbf.add_shard()
        sbf.add("new-item")
        self.assertNotIn("old-item", _TailOnly(sbf, 1))
        self.assertIn("old-item", sbf)


class _TailOnly:
    """只查部分片的残缺视图，用来验证漏片即假阴性。"""

    def __init__(self, sbf, skip):
        self._shards = sbf.shards[skip:]

    def __contains__(self, item):
        return any(item in shard for shard in self._shards)


class TestOverallFpRate(unittest.TestCase):
    def test_empty_followers_do_not_change_rate(self):
        sbf = ShardBloomFilter(capacity=1000, fp_rate=0.01)
        before = sbf.fp_rate()
        sbf.add_shard()
        sbf.add_shard()
        self.assertEqual(before, 0.0)
        self.assertEqual(sbf.fp_rate(), 0.0)

    def test_single_loaded_shard_matches_target(self):
        sbf = ShardBloomFilter(capacity=2000, fp_rate=0.01)
        _fill(sbf, 0, 2000)
        # m、k 都取整，写满时的真实率按精确填充率公式走，贴近但略高于 0.01
        self.assertAlmostEqual(sbf.fp_rate(), 0.01, delta=0.001)

    def test_overall_rate_is_union_not_per_shard(self):
        sbf = ShardBloomFilter(capacity=1000, fp_rate=0.01)
        _fill(sbf, 0, 1000)
        sbf.add_shard()
        _fill(sbf, 1_000_000, 1000)

        per_shard = [ShardBloomFilter._shard_fp_rate(shard) for shard in sbf.shards]
        expected = 1.0 - (1.0 - per_shard[0]) * (1.0 - per_shard[1])
        self.assertAlmostEqual(sbf.fp_rate(), expected)
        # 整体率严格高于任意单片，绝不能拿单片率糊弄
        self.assertGreater(sbf.fp_rate(), max(per_shard))

    def test_empirical_rate_tracks_formula(self):
        sbf = ShardBloomFilter(capacity=1000, fp_rate=0.01)
        _fill(sbf, 0, 2000)  # 首片塞满还继续写，模拟容量撑不住
        sbf.add_shard()
        _fill(sbf, 10_000_000, 1000)

        rng = random.Random(20240920)
        probes = 20000
        hits = sum(("probe-%d" % rng.randrange(10 ** 12)) in sbf for _ in range(probes))
        observed = hits / probes
        self.assertAlmostEqual(observed, sbf.fp_rate(), delta=0.02)


class TestLegacyFormat(unittest.TestCase):
    def test_reads_blm1_single_instance_blob(self):
        legacy = BloomFilter(capacity=1000, fp_rate=0.01)
        for word in ("legacy-a", "legacy-b", "legacy-c"):
            legacy.add(word)

        sbf = ShardBloomFilter.from_bytes(legacy.to_bytes())
        self.assertEqual(len(sbf.shards), 1)
        for word in ("legacy-a", "legacy-b", "legacy-c"):
            self.assertIn(word, sbf)
        self.assertNotIn("legacy-missing", sbf)
        self.assertEqual(len(sbf), 3)

    def test_legacy_shard_can_grow_and_roundtrip(self):
        legacy = BloomFilter(capacity=100, fp_rate=0.05)
        legacy.add("old")
        sbf = ShardBloomFilter.from_bytes(legacy.to_bytes())
        sbf.add_shard()
        sbf.add("new")

        restored = ShardBloomFilter.from_bytes(sbf.to_bytes())
        self.assertTrue(sbf.to_bytes().startswith(MAGIC))
        self.assertIn("old", restored)
        self.assertIn("new", restored)
        self.assertEqual(len(restored.shards), 2)


class TestShardCap(unittest.TestCase):
    def test_refuses_to_grow_past_limit(self):
        sbf = ShardBloomFilter(capacity=100, fp_rate=0.01, max_shards=3)
        sbf.add_shard()
        sbf.add_shard()
        self.assertEqual(len(sbf.shards), 3)
        with self.assertRaises(ShardCapacityError):
            sbf.add_shard()
        # 兜底只拦添片，不影响已有片的查询
        self.assertNotIn("anything", sbf)

    def test_bytes_roundtrip_preserves_limit_and_fp(self):
        sbf = ShardBloomFilter(capacity=500, fp_rate=0.02, max_shards=5)
        _fill(sbf, 0, 60)
        sbf.add_shard()
        _fill(sbf, 9000, 40)
        blob = sbf.to_bytes()
        restored = ShardBloomFilter.from_bytes(blob)
        self.assertEqual(restored.max_shards, 5)
        self.assertAlmostEqual(restored.target_fp_rate, 0.02, places=6)
        self.assertEqual(len(restored), 100)
        self.assertEqual(restored.fp_rate(), sbf.fp_rate())
        for i in list(range(60)) + list(range(9000, 9040)):
            self.assertIn("evt-%d" % i, restored)


class TestConcurrentAddDuringGrowth(unittest.TestCase):
    def test_no_writes_lost_while_shards_are_added(self):
        sbf = ShardBloomFilter(capacity=500, fp_rate=0.01, max_shards=8)
        stop = threading.Event()
        errors = []

        def grower():
            while not stop.is_set():
                try:
                    sbf.add_shard()
                except ShardCapacityError:
                    return

        def writer(start, count):
            try:
                for offset in range(count):
                    sbf.add("c-%d-%d" % (start, offset))
            except Exception as exc:  # pragma: no cover - 失败即暴露
                errors.append(exc)

        threads = [
            threading.Thread(target=writer, args=(wid * 100000, 400))
            for wid in range(8)
        ]
        grow = threading.Thread(target=grower)
        for thread in threads:
            thread.start()
        grow.start()
        for thread in threads:
            thread.join()
        stop.set()
        grow.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(sbf), 8 * 400)
        # 添片期间写进去的每一条都还能查到，没有一条丢
        for wid in range(8):
            for offset in range(400):
                self.assertIn("c-%d-%d" % (wid * 100000, offset), sbf)


if __name__ == "__main__":
    unittest.main()
