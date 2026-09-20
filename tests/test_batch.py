"""batch 现有行为的锁定测试（确定性，不依赖时序）。"""

import threading
import unittest

from tracectx.batch import ItemFailure, first_failure, map_batch


class TestMapBatch(unittest.TestCase):
    def test_results_keep_order(self):
        self.assertEqual(map_batch(str.upper, ["a", "b", "c"], workers=3), ["A", "B", "C"])

    def test_empty_items(self):
        self.assertEqual(map_batch(str.upper, [], workers=4), [])

    def test_workers_below_one_is_one(self):
        self.assertEqual(map_batch(lambda x: x * 2, [1, 2, 3], workers=0), [2, 4, 6])

    def test_more_workers_than_items(self):
        self.assertEqual(map_batch(lambda x: x + 1, [1, 2], workers=8), [2, 3])

    def test_every_item_processed_once(self):
        seen = []
        lock = threading.Lock()

        def fn(x):
            with lock:
                seen.append(x)
            return x

        items = list(range(50))
        results = map_batch(fn, items, workers=5)
        self.assertEqual(sorted(seen), items)
        self.assertEqual(results, items)

    def test_failure_isolated_at_index(self):
        def fn(x):
            if x == 2:
                raise ValueError("bad")
            return x * 10

        results = map_batch(fn, [1, 2, 3], workers=1)
        self.assertEqual(results[0], 10)
        self.assertIsInstance(results[1], ItemFailure)
        self.assertEqual(results[2], 30)

    def test_failure_carries_item_and_error(self):
        marker = ValueError("boom")

        def fn(x):
            raise marker

        results = map_batch(fn, ["x"], workers=1)
        self.assertIs(results[0].item, "x")
        self.assertIs(results[0].error, marker)

    def test_neighbor_survives_same_chunk(self):
        def fn(x):
            if x == "bad":
                raise RuntimeError("no")
            return "ok:" + x

        results = map_batch(fn, ["a", "bad", "b"], workers=1)
        shown = ["F" if isinstance(r, ItemFailure) else r for r in results]
        self.assertEqual(shown, ["ok:a", "F", "ok:b"])

    def test_chunks_actually_concurrent(self):
        barrier = threading.Barrier(3, timeout=5)

        def fn(x):
            barrier.wait()
            return x

        self.assertEqual(map_batch(fn, [1, 2, 3], workers=3), [1, 2, 3])


class TestFirstFailure(unittest.TestCase):
    def test_none_when_all_ok(self):
        self.assertIsNone(first_failure([1, 2, 3]))

    def test_returns_first_failure(self):
        f1 = ItemFailure("a", ValueError())
        f2 = ItemFailure("b", ValueError())
        self.assertIs(first_failure([1, f1, f2]), f1)


if __name__ == "__main__":
    unittest.main()
