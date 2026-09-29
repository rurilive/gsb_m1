"""哈希原语与定容换算的行为锁定。盐与算法一改，线上数据与落盘格式全对不上。"""

import unittest

from bloomx.hashing import bit_indexes, digest, hash_pair, sizing


class TestDigest(unittest.TestCase):
    def test_frozen_value(self):
        # 冻结摘要：换盐、换算法都会让这里失守
        self.assertEqual(
            digest("https://example.com/a"),
            bytes.fromhex("c2a3efd4f7d4a73a65ab21f9d88d8ecda7873758a0565a95bb8b00ee957a1b99"),
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

    def test_salt_changes_pair(self):
        self.assertNotEqual(hash_pair("k", 0), hash_pair("k", 7))


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


class TestSizing(unittest.TestCase):
    def test_bigger_capacity_more_bits(self):
        big_bits, _ = sizing(10000, 0.01)
        small_bits, _ = sizing(10, 0.01)
        self.assertGreater(big_bits, small_bits)

    def test_tighter_rate_more_bits(self):
        loose_bits, _ = sizing(100, 0.1)
        tight_bits, _ = sizing(100, 0.001)
        self.assertGreater(tight_bits, loose_bits)

    def test_num_hashes_at_least_one(self):
        for cap in (1, 8, 100, 100000):
            _, k = sizing(cap, 0.01)
            self.assertGreaterEqual(k, 1)

    def test_bad_capacity_rejected(self):
        with self.assertRaises(ValueError):
            sizing(0, 0.01)

    def test_bad_rate_rejected(self):
        with self.assertRaises(ValueError):
            sizing(10, 1.5)


if __name__ == "__main__":
    unittest.main()
