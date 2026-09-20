"""档位划分的既有行为锁定。"""

import unittest

from bufpool.errors import InvalidSize
from bufpool.tiers import OVERSIZE, TIERS, check_size, tier_key, tier_of


class TierTest(unittest.TestCase):
    def test_tiers_are_ascending_and_start_at_256(self):
        self.assertEqual(TIERS[0], 256)
        self.assertEqual(list(TIERS), sorted(TIERS))
        self.assertEqual(len(set(TIERS)), len(TIERS))

    def test_tier_of_rounds_up_to_nearest_tier(self):
        self.assertEqual(tier_of(1), 256)
        self.assertEqual(tier_of(256), 256)
        self.assertEqual(tier_of(257), 1024)
        self.assertEqual(tier_of(1024), 1024)
        self.assertEqual(tier_of(65535), 65536)
        self.assertEqual(tier_of(65536), 65536)

    def test_oversize_has_no_tier(self):
        self.assertIsNone(tier_of(65537))
        self.assertIsNone(tier_of(10 * 1024 * 1024))
        self.assertEqual(tier_key(65537), OVERSIZE)

    def test_tier_key_matches_tier_for_normal_sizes(self):
        self.assertEqual(tier_key(100), 256)
        self.assertEqual(tier_key(4096), 4096)

    def test_check_size_rejects_non_positive_and_non_int(self):
        for bad in (0, -1, -4096, 1.5, "256", None, True, False):
            with self.assertRaises(InvalidSize):
                check_size(bad)

    def test_check_size_passes_positive_int_through(self):
        self.assertEqual(check_size(1), 1)
        self.assertEqual(check_size(65536), 65536)


if __name__ == "__main__":
    unittest.main()
