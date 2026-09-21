"""哈希原语的行为锁定。盐和算法一改，线上数据与落盘格式全对不上。"""

import unittest

from crawlkit.hashing import bit_indexes, bucket_index, digest, fingerprint, hash_pair


class TestDigest(unittest.TestCase):
    def test_frozen_value(self):
        # 冻结摘要：换盐、换算法都会让这里失守
        self.assertEqual(
            digest("https://example.com/a"),
            bytes.fromhex("d42152460db18878a05ad6124e3a67fb8c22c3b2dec1e42b8eeea891e998dce4"),
        )

    def test_str_and_bytes_agree(self):
        self.assertEqual(digest("abc"), digest(b"abc"))

    def test_distinct_keys_distinct_digests(self):
        self.assertNotEqual(digest("a"), digest("b"))


class TestHashPair(unittest.TestCase):
    def test_two_unsigned_64(self):
        h1, h2 = hash_pair("k")
        for h in (h1, h2):
            self.assertGreaterEqual(h, 0)
            self.assertLess(h, 1 << 64)

    def test_stable(self):
        self.assertEqual(hash_pair("k"), hash_pair("k"))


class TestBitIndexes(unittest.TestCase):
    def test_count_and_range(self):
        idxs = list(bit_indexes(123456789, 987654321, 5, 1000))
        self.assertEqual(len(idxs), 5)
        for i in idxs:
            self.assertGreaterEqual(i, 0)
            self.assertLess(i, 1000)

    def test_bad_args_rejected(self):
        with self.assertRaises(ValueError):
            list(bit_indexes(1, 2, 0, 10))
        with self.assertRaises(ValueError):
            list(bit_indexes(1, 2, 3, 0))


class TestBucketIndex(unittest.TestCase):
    def test_range(self):
        for h in (0, 1, 123456789, (1 << 64) - 1):
            self.assertGreaterEqual(bucket_index(h, 16), 0)
            self.assertLess(bucket_index(h, 16), 16)

    def test_zero_buckets_rejected(self):
        with self.assertRaises(ValueError):
            bucket_index(1, 0)


class TestFingerprint(unittest.TestCase):
    def test_never_zero_and_in_range(self):
        for i in range(5000):
            fp = fingerprint(i * 2654435761, 8)
            self.assertGreaterEqual(fp, 1)
            self.assertLess(fp, 256)

    def test_stable(self):
        self.assertEqual(fingerprint(42, 12), fingerprint(42, 12))

    def test_bad_bits_rejected(self):
        with self.assertRaises(ValueError):
            fingerprint(1, 0)


if __name__ == "__main__":
    unittest.main()
