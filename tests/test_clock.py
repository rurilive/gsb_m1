"""基线测试：锁住整数时钟现在的行为，一字不改。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vcbox import Clock


class ClockBaselineTest(unittest.TestCase):
    def test_default_starts_at_zero(self):
        self.assertEqual(Clock().value, 0)

    def test_tick_increments(self):
        c = Clock()
        self.assertEqual(c.tick(), 1)
        self.assertEqual(c.tick(), 2)
        self.assertEqual(c.value, 2)

    def test_init_value(self):
        self.assertEqual(Clock(5).value, 5)

    def test_equality(self):
        self.assertEqual(Clock(3), Clock(3))
        self.assertNotEqual(Clock(3), Clock(4))

    def test_ordering(self):
        self.assertTrue(Clock(1) < Clock(2))
        self.assertTrue(Clock(2) > Clock(1))
        self.assertTrue(Clock(2) <= Clock(2))

    def test_negative_init_raises(self):
        with self.assertRaises(ValueError):
            Clock(-1)

    def test_non_int_init_raises(self):
        with self.assertRaises(TypeError):
            Clock("x")


if __name__ == "__main__":
    unittest.main()
