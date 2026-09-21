"""IndexedHeap 现有行为的锁定测试。"""

import unittest

from taskheap import IndexedHeap


class TestPushPop(unittest.TestCase):
    def test_empty_and_single_entry(self):
        heap = IndexedHeap()
        self.assertIsNone(heap.pop_min())
        heap.push(7, "only")
        entry = heap.pop_min()
        self.assertEqual((entry.task_id, entry.key()), ("only", (7, "only")))
        self.assertIsNone(heap.pop_min())

    def test_pop_follows_priority(self):
        heap = IndexedHeap()
        for prio, task_id in ((5, "e"), (1, "a"), (9, "i"), (3, "c")):
            heap.push(prio, task_id)
        self.assertEqual([heap.pop_min().task_id for _ in range(4)],
                         ["a", "c", "e", "i"])

    def test_interleaved_push_pop(self):
        heap = IndexedHeap()
        heap.push(4, "d")
        heap.push(2, "b")
        self.assertEqual(heap.pop_min().task_id, "b")
        heap.push(1, "a")
        heap.push(3, "c")
        self.assertEqual([heap.pop_min().task_id for _ in range(3)],
                         ["a", "c", "d"])

    def test_duplicate_priorities_are_all_served(self):
        heap = IndexedHeap()
        for task_id in ("t1", "t2", "t3"):
            heap.push(6, task_id)
        served = [heap.pop_min().task_id for _ in range(3)]
        self.assertEqual(sorted(served), ["t1", "t2", "t3"])
        self.assertEqual(len(heap), 0)


class TestObservation(unittest.TestCase):
    def test_size_len_capacity_track_entries(self):
        heap = IndexedHeap()
        self.assertEqual((heap.size(), len(heap), heap.capacity()), (0, 0, 0))
        for index in range(20):
            heap.push(index, "t%d" % index)
            self.assertGreaterEqual(heap.capacity(), heap.size())
        self.assertEqual((heap.size(), len(heap)), (20, 20))
        heap.pop_min()
        self.assertEqual(heap.size(), 19)

    def test_peek_does_not_remove(self):
        heap = IndexedHeap()
        self.assertIsNone(heap.peek())
        heap.push(2, "b")
        heap.push(1, "a")
        self.assertEqual(heap.peek().task_id, "a")
        self.assertEqual(heap.size(), 2)

    def test_live_entries_only_covers_live_records(self):
        heap = IndexedHeap()
        heap.push(1, "a")
        heap.push(2, "b")
        heap.pop_min()
        entries = heap.live_entries()
        self.assertEqual([entry.task_id for entry in entries], ["b"])
