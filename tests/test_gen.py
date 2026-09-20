"""IdGenerator 行为基线。"""
import unittest

from idgen import IdGenerator


class FakeClock:
    def __init__(self, ms):
        self.ms = ms

    def __call__(self):
        return self.ms / 1000.0


class TestIdGenerator(unittest.TestCase):
    def test_ids_increase_within_same_ms(self):
        clock = FakeClock(1700000001000)
        g = IdGenerator(clock)
        a, b, c = g.next_id(), g.next_id(), g.next_id()
        self.assertLess(a, b)
        self.assertLess(b, c)

    def test_timestamp_part_encodes_clock(self):
        g = IdGenerator(FakeClock(1700000001000))
        self.assertEqual(g.next_id() >> 16, 1000)

    def test_new_ms_resets_counter(self):
        clock = FakeClock(1700000001000)
        g = IdGenerator(clock)
        g.next_id()
        clock.ms = 1700000001001
        self.assertEqual(g.next_id() & 0xFFFF, 0)

    def test_returns_int(self):
        g = IdGenerator(FakeClock(1700000001000))
        self.assertIsInstance(g.next_id(), int)


if __name__ == "__main__":
    unittest.main()
