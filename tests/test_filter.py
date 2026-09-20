"""BloomFilter 行为基线：格式、尺寸公式、写读语义与序列化。"""
import unittest

from bloomx import BloomFilter
from bloomx.filter import MAGIC


class TestSizing(unittest.TestCase):
    def test_bits_and_hashes_follow_formula(self):
        bf = BloomFilter(capacity=1000, fp_rate=0.01)
        self.assertEqual(bf.num_bits, 9586)
        self.assertEqual(bf.num_hashes, 7)

    def test_sizing_scales_with_capacity(self):
        bf = BloomFilter(capacity=100, fp_rate=0.05)
        self.assertEqual(bf.num_bits, 624)
        self.assertEqual(bf.num_hashes, 4)
        big = BloomFilter(capacity=10000, fp_rate=0.001)
        self.assertEqual(big.num_bits, 143776)
        self.assertEqual(big.num_hashes, 10)

    def test_rejects_bad_args(self):
        with self.assertRaises(ValueError):
            BloomFilter(capacity=0)
        with self.assertRaises(ValueError):
            BloomFilter(capacity=100, fp_rate=0.0)
        with self.assertRaises(ValueError):
            BloomFilter(capacity=100, fp_rate=1.0)


class TestMembership(unittest.TestCase):
    def setUp(self):
        self.bf = BloomFilter(capacity=1000, fp_rate=0.01)
        for word in ["alpha", "beta", "gamma"]:
            self.bf.add(word)

    def test_added_items_are_present(self):
        self.assertIn("alpha", self.bf)
        self.assertIn("beta", self.bf)
        self.assertIn("gamma", self.bf)

    def test_absent_item_is_reported_absent(self):
        self.assertNotIn("delta", self.bf)

    def test_no_false_negatives_after_many_adds(self):
        words = ["k%d" % i for i in range(500)]
        for w in words:
            self.bf.add(w)
        for w in words:
            self.assertIn(w, self.bf)

    def test_contains_returns_bool(self):
        self.assertIsInstance("alpha" in self.bf, bool)

    def test_accepts_bytes_and_str(self):
        self.bf.add(b"\x00\x01\x02")
        self.assertIn(b"\x00\x01\x02", self.bf)
        self.bf.add(12345)
        self.assertIn(12345, self.bf)


class TestCount(unittest.TestCase):
    def test_len_counts_every_add(self):
        bf = BloomFilter(capacity=100, fp_rate=0.01)
        self.assertEqual(len(bf), 0)
        bf.add("a")
        bf.add("a")
        self.assertEqual(len(bf), 2)


class TestSerialization(unittest.TestCase):
    def test_roundtrip_preserves_membership(self):
        bf = BloomFilter(capacity=1000, fp_rate=0.01)
        for word in ["alpha", "beta", "gamma"]:
            bf.add(word)
        blob = bf.to_bytes()
        restored = BloomFilter.from_bytes(blob)
        self.assertEqual(restored.num_bits, bf.num_bits)
        self.assertEqual(restored.num_hashes, bf.num_hashes)
        self.assertEqual(len(restored), len(bf))
        for word in ["alpha", "beta", "gamma"]:
            self.assertIn(word, restored)
        self.assertNotIn("delta", restored)

    def test_blob_starts_with_magic(self):
        bf = BloomFilter(capacity=100, fp_rate=0.01)
        self.assertTrue(bf.to_bytes().startswith(MAGIC))

    def test_roundtrip_is_byte_stable(self):
        bf = BloomFilter(capacity=100, fp_rate=0.01)
        bf.add("x")
        self.assertEqual(bf.to_bytes(), BloomFilter.from_bytes(bf.to_bytes()).to_bytes())

    def test_from_bytes_rejects_bad_magic(self):
        bf = BloomFilter(capacity=100, fp_rate=0.01)
        blob = b"XXXX" + bf.to_bytes()[4:]
        with self.assertRaises(ValueError):
            BloomFilter.from_bytes(blob)

    def test_from_bytes_rejects_truncated_blob(self):
        with self.assertRaises(ValueError):
            BloomFilter.from_bytes(b"BLM")


if __name__ == "__main__":
    unittest.main()
