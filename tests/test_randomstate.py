"""RandomState 现有行为的锁定：同 seed 同序列，跨实例可复现。"""

import unittest

from bloomx.randomstate import RandomState


class TestRandomState(unittest.TestCase):
    def test_same_seed_same_stream(self):
        a = RandomState(1234)
        b = RandomState(1234)
        for _ in range(50):
            self.assertEqual(a.getrandbits(32), b.getrandbits(32))

    def test_different_seed_differs(self):
        a = RandomState(1)
        b = RandomState(2)
        self.assertNotEqual(
            [a.getrandbits(32) for _ in range(8)],
            [b.getrandbits(32) for _ in range(8)],
        )

    def test_below_range(self):
        rs = RandomState(7)
        for _ in range(200):
            v = rs.below(16)
            self.assertGreaterEqual(v, 0)
            self.assertLess(v, 16)

    def test_salt_never_zero(self):
        rs = RandomState(99)
        for _ in range(200):
            self.assertNotEqual(rs.salt(), 0)

    def test_fork_reproducible(self):
        a = RandomState(5).fork(1)
        b = RandomState(5).fork(1)
        self.assertEqual(
            [a.getrandbits(16) for _ in range(10)],
            [b.getrandbits(16) for _ in range(10)],
        )

    def test_bad_seed_type_rejected(self):
        with self.assertRaises((TypeError, ValueError)):
            RandomState("nope")


if __name__ == "__main__":
    unittest.main()
