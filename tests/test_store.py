"""DedupStore 现有行为的锁定测试。"""

import unittest

from crawlkit import NotSupportedError
from crawlkit.store import DedupStore

# 线上第一批落盘的快照，mark("u0") 到 mark("u9") 后 dump 出来的原样字节。
# 存量文件就长这样，读回时格式不许挑肥拣瘦。
LEGACY_BLOB = bytes.fromhex(
    "44445331000000000000000a000000000000000000000000000000003f847ae147ae147b"
    "44424c4d0000026600000007000000403f847ae147ae147b000000000000000a"
    "060004020000120020020040400080000108401004010100000810004000800060081"
    "48050001101000000000c0012000000282011400100040042c02048020004000010410140050080140020"
)


class TestDedupStore(unittest.TestCase):
    def test_mark_then_duplicate(self):
        s = DedupStore(capacity=100)
        s.mark("u1")
        self.assertTrue(s.is_duplicate("u1"))
        self.assertFalse(s.is_duplicate("nope-1"))
        self.assertFalse(s.is_duplicate("nope-2"))

    def test_stats_counters(self):
        s = DedupStore(capacity=100)
        s.mark("u1")
        s.is_duplicate("u1")
        s.is_duplicate("nope")
        st = s.stats()
        self.assertEqual(st["marks"], 1)
        self.assertEqual(st["queries"], 2)
        self.assertEqual(st["duplicates"], 1)
        self.assertEqual(st["filter"]["added"], 1)

    def test_stats_is_fresh_dict(self):
        s = DedupStore(capacity=10)
        st = s.stats()
        st["marks"] = 99
        self.assertEqual(s.stats()["marks"], 0)

    def test_retry_unsupported_on_bloom(self):
        s = DedupStore(capacity=10)
        s.mark("u1")
        with self.assertRaises(NotSupportedError):
            s.retry("u1")
        # 抛异常不能顺手把已有标记擦掉
        self.assertTrue(s.is_duplicate("u1"))

    def test_round_trip(self):
        s = DedupStore(capacity=50, fp_rate=0.02)
        for i in range(10):
            s.mark("u%d" % i)
        s.is_duplicate("u0")
        blob = s.to_bytes()
        back = DedupStore.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(back.fp_rate, s.fp_rate)
        self.assertEqual(back.capacity, s.capacity)
        st = back.stats()
        self.assertEqual(st["marks"], 10)
        self.assertEqual(st["queries"], 1)
        self.assertTrue(back.is_duplicate("u3"))

    def test_legacy_snapshot_still_loads(self):
        back = DedupStore.from_bytes(LEGACY_BLOB)
        self.assertEqual(back.stats()["marks"], 10)
        for i in range(10):
            self.assertTrue(back.is_duplicate("u%d" % i))
        self.assertFalse(back.is_duplicate("never-seen"))
        # 老快照读回来还得能接着标记
        back.mark("u99")
        self.assertTrue(back.is_duplicate("u99"))

    def test_bad_magic_rejected(self):
        blob = bytearray(DedupStore(capacity=10).to_bytes())
        blob[0:4] = b"XXXX"
        with self.assertRaises(ValueError):
            DedupStore.from_bytes(bytes(blob))

    def test_truncated_rejected(self):
        with self.assertRaises(ValueError):
            DedupStore.from_bytes(b"DD")

    def test_bad_capacity_rejected(self):
        with self.assertRaises(ValueError):
            DedupStore(capacity=0)


if __name__ == "__main__":
    unittest.main()
