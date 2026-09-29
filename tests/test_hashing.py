"""hashing 现有原语的锁定测试：摘要、双重哈希与最优参数换算。"""

import unittest

from bloomchain.hashing import (
    bit_indexes,
    digest,
    estimate_cardinality,
    hash_pair,
    optimal_params,
    sizing,
)


class TestDigest(unittest.TestCase):
    def test_digest_shape_and_stability(self):
        self.assertEqual(len(digest("k")), 32)
        self.assertEqual(digest("k"), digest("k"))

    def test_str_and_bytes_agree(self):
        self.assertEqual(digest("hi"), digest(b"hi"))

    def test_distinct_keys_differ(self):
        self.assertNotEqual(digest("a"), digest("b"))


class TestHashPair(unittest.TestCase):
    def test_two_unsigned_64(self):
        h1, h2 = hash_pair("k")
        self.assertTrue(0 <= h1 < (1 << 64))
        self.assertTrue(0 <= h2 < (1 << 64))

    def test_salt_changes_pair(self):
        self.assertNotEqual(hash_pair("k"), hash_pair("k", salt=12345))


class TestBitIndexes(unittest.TestCase):
    def test_in_range_and_count(self):
        h1, h2 = hash_pair("k")
        idxs = list(bit_indexes(h1, h2, 4, 64))
        self.assertEqual(len(idxs), 4)
        for i in idxs:
            self.assertTrue(0 <= i < 64)

    def test_bad_args_rejected(self):
        with self.assertRaises(ValueError):
            list(bit_indexes(1, 2, 0, 64))
        with self.assertRaises(ValueError):
            list(bit_indexes(1, 2, 3, 0))


class TestOptimalParams(unittest.TestCase):
    def test_known_small_case(self):
        num_bits, num_hashes = optimal_params(100, 0.01)
        self.assertEqual(num_bits, 959)
        self.assertEqual(num_hashes, 7)

    def test_sizing_is_alias(self):
        self.assertEqual(sizing(100, 0.01), optimal_params(100, 0.01))

    def test_bad_args_rejected(self):
        with self.assertRaises(ValueError):
            optimal_params(0, 0.01)
        with self.assertRaises(ValueError):
            optimal_params(100, 0.0)
        with self.assertRaises(ValueError):
            optimal_params(100, 1.0)


class TestEstimateCardinality(unittest.TestCase):
    def test_empty_is_zero(self):
        self.assertEqual(estimate_cardinality(1000, 0), 0.0)

    def test_rough_scale(self):
        est = estimate_cardinality(1000, 500)
        self.assertGreater(est, 100)
        self.assertLess(est, 1500)


if __name__ == "__main__":
    unittest.main()