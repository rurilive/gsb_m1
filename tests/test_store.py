"""TagStore 行为基线：记录读写、倒排表与订阅回调的既有语义。"""

import unittest

from bitag.store import TagStore


class TagStoreTest(unittest.TestCase):
    def setUp(self):
        self.store = TagStore()

    def test_add_and_read_back(self):
        self.store.add(1, [7, 3])
        self.store.add(2, [3])
        self.assertEqual(self.store.get(1), (3, 7))
        self.assertEqual(self.store.get(2), (3,))
        self.assertEqual(self.store.ids(), [1, 2])
        self.assertEqual(self.store.count(), 2)

    def test_get_missing_record_is_empty_tuple(self):
        self.assertEqual(self.store.get(99), ())

    def test_add_same_labels_again_is_noop(self):
        self.assertTrue(self.store.add(1, [3, 7]))
        self.assertFalse(self.store.add(1, [7, 3, 3]))
        self.assertEqual(self.store.stats()["updates"], 1)
        self.assertEqual(self.store.stats()["entries"], 2)

    def test_add_replaces_labels(self):
        self.store.add(1, [3, 7])
        self.store.add(2, [3])
        self.assertTrue(self.store.add(1, [9]))
        self.assertEqual(self.store.get(1), (9,))
        self.assertEqual(self.store.postings(3), {2})
        self.assertEqual(self.store.postings(9), {1})

    def test_emptied_label_leaves_the_table(self):
        self.store.add(1, [5])
        self.store.add(2, [5])
        self.store.remove(2)
        self.assertEqual(self.store.labels(), [5])
        self.store.remove(1)
        self.assertEqual(self.store.labels(), [])
        self.assertEqual(self.store.postings(5), set())

    def test_remove_reports_and_is_idempotent(self):
        self.store.add(1, [5])
        self.assertTrue(self.store.remove(1))
        self.assertFalse(self.store.remove(1))
        self.assertEqual(self.store.stats()["updates"], 2)
        self.assertEqual(self.store.stats()["records"], 0)

    def test_postings_is_a_detached_copy(self):
        self.store.add(1, [5])
        got = self.store.postings(5)
        got.add(12345)
        got.discard(1)
        self.assertEqual(self.store.postings(5), {1})

    def test_unknown_label_gives_empty_set(self):
        self.assertEqual(self.store.postings(404), set())

    def test_record_without_labels_is_kept(self):
        self.store.add(1, [])
        self.assertEqual(self.store.get(1), ())
        self.assertEqual(self.store.ids(), [1])
        self.assertEqual(self.store.labels(), [])

    def test_duplicate_labels_collapse(self):
        self.store.add(1, [4, 4, 4])
        self.assertEqual(self.store.get(1), (4,))
        self.assertEqual(self.store.stats()["entries"], 1)

    def test_ids_and_labels_sorted(self):
        for rid, labels in ((9, [8, 2]), (1, [8]), (5, [4])):
            self.store.add(rid, labels)
        self.assertEqual(self.store.ids(), [1, 5, 9])
        self.assertEqual(self.store.labels(), [2, 4, 8])

    def test_bad_ids_rejected(self):
        for bad in (-1, 2 ** 32, "3", 1.5, True, None):
            with self.assertRaises(ValueError):
                self.store.add(bad, [1])
            with self.assertRaises(ValueError):
                self.store.add(1, [bad])

    def test_subscribe_sees_updates_and_removals(self):
        seen = []
        self.store.subscribe(
            lambda rid, old, new: seen.append((rid, old, new)))
        self.store.add(1, [3])
        self.store.add(1, [3])
        self.store.add(1, [4])
        self.store.remove(1)
        self.store.remove(1)
        self.assertEqual(
            seen, [(1, None, (3,)), (1, (3,), (4,)), (1, (4,), None)])

    def test_unsubscribe_stops_callbacks(self):
        seen = []
        callback = lambda rid, old, new: seen.append(rid)  # noqa: E731
        self.store.subscribe(callback)
        self.store.add(1, [3])
        self.store.unsubscribe(callback)
        self.store.add(2, [3])
        self.assertEqual(seen, [1])

    def test_stats_shape(self):
        self.store.add(1, [3, 7])
        self.store.add(2, [7])
        stats = self.store.stats()
        self.assertEqual(stats["records"], 2)
        self.assertEqual(stats["labels"], 2)
        self.assertEqual(stats["entries"], 3)
        self.assertEqual(stats["updates"], 2)


if __name__ == "__main__":
    unittest.main()
