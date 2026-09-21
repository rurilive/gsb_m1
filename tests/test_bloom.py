"""BloomFilter 现有行为的锁定测试。"""

import unittest

from crawlkit.bloom import BloomFilter


class TestBloomFilter(unittest.TestCase):
    def test_added_keys_always_hit(self):
        bf = BloomFilter(capacity=100)
        keys = ["u%d" % i for i in range(100)]
        for k in keys:
            bf.add(k)
        for k in keys:
            self.assertIn(k, bf)

    def test_missing_keys_mostly_miss(self):
        bf = BloomFilter(capacity=50, fp_rate=0.01)
        for i in range(50):
            bf.add("in-%d" % i)
        misses = sum(1 for i in range(500) if ("out-%d" % i) not in bf)
        self.assertGreater(misses, 400)

    def test_len_counts_adds(self):
        bf = BloomFilter(capacity=10)
        bf.add("a")
        bf.add("a")
        self.assertEqual(len(bf), 2)

    def test_capacity_drives_sizing(self):
        big = BloomFilter(capacity=10000, fp_rate=0.01)
        small = BloomFilter(capacity=10, fp_rate=0.01)
        self.assertGreater(big.num_bits, small.num_bits)
        self.assertGreaterEqual(small.num_hashes, 1)

    def test_stats_is_fresh_dict(self):
        bf = BloomFilter(capacity=10)
        s = bf.stats()
        s["added"] = 99
        self.assertEqual(bf.stats()["added"], 0)

    def test_round_trip_byte_identical(self):
        bf = BloomFilter(capacity=100, fp_rate=0.02)
        for i in range(40):
            bf.add("k%d" % i)
        blob = bf.to_bytes()
        back = BloomFilter.from_bytes(blob)
        self.assertEqual(back.to_bytes(), blob)
        self.assertEqual(back.capacity, bf.capacity)
        self.assertEqual(back.fp_rate, bf.fp_rate)
        self.assertEqual(len(back), len(bf))

    def test_round_trip_keeps_hits_and_false_positives(self):
        bf = BloomFilter(capacity=20, fp_rate=0.05)
        for i in range(20):
            bf.add("x%d" % i)
        back = BloomFilter.from_bytes(bf.to_bytes())
        for i in range(2000):
            q = "y%d" % i
            self.assertEqual(q in back, q in bf)

    def test_bad_magic_rejected(self):
        blob = bytearray(BloomFilter(capacity=10).to_bytes())
        blob[0:4] = b"NOPE"
        with self.assertRaises(ValueError):
            BloomFilter.from_bytes(bytes(blob))

    def test_truncated_rejected(self):
        with self.assertRaises(ValueError):
            BloomFilter.from_bytes(b"short")

    def test_payload_length_checked(self):
        blob = BloomFilter(capacity=10).to_bytes()
        with self.assertRaises(ValueError):
            BloomFilter.from_bytes(blob[:-1])

    def test_bad_capacity_rejected(self):
        with self.assertRaises(ValueError):
            BloomFilter(capacity=0)

    def test_bad_fp_rate_rejected(self):
        with self.assertRaises(ValueError):
            BloomFilter(capacity=10, fp_rate=1.5)


if __name__ == "__main__":
    unittest.main()
