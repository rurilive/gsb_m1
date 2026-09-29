"""idmill 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from idmill.counter import Counter
from idmill import Counter as ExportedCounter


class TestCounter(unittest.TestCase):
    def test_default_starts_at_zero(self):
        counter = Counter()
        self.assertEqual(counter.value, 0)
        self.assertEqual(counter.next_id(), 0)

    def test_returns_value_then_increments(self):
        counter = Counter()
        self.assertEqual(counter.next_id(), 0)
        self.assertEqual(counter.next_id(), 1)
        self.assertEqual(counter.next_id(), 2)
        self.assertEqual(counter.value, 3)

    def test_custom_start(self):
        counter = Counter(start=100)
        self.assertEqual(counter.next_id(), 100)
        self.assertEqual(counter.next_id(), 101)

    def test_ids_are_unique_and_increasing(self):
        counter = Counter()
        ids = [counter.next_id() for _ in range(5)]
        self.assertEqual(ids, [0, 1, 2, 3, 4])
        self.assertEqual(len(set(ids)), len(ids))

    def test_package_exports_counter(self):
        self.assertIs(ExportedCounter, Counter)


if __name__ == "__main__":
    unittest.main()
