"""PageTable 现有行为的锁定测试。"""

import threading
import unittest

from vecpage.page import PageTable


def make_table():
    return PageTable()


class TestMapAndWalk(unittest.TestCase):
    def test_walk_unknown_page_is_none(self):
        t = make_table()
        self.assertIsNone(t.walk(9, 1))

    def test_map_then_walk_same_version(self):
        t = make_table()
        t.map(1, 100, 1)
        self.assertEqual(t.walk(1, 1), 100)

    def test_mapping_persists_into_later_versions(self):
        t = make_table()
        t.map(1, 100, 1)
        self.assertEqual(t.walk(1, 7), 100)

    def test_newer_version_supersedes(self):
        t = make_table()
        t.map(1, 100, 1)
        t.map(1, 200, 2)
        self.assertEqual(t.walk(1, 2), 200)

    def test_latest_frame_visible_at_latest_version(self):
        t = make_table()
        t.map(4, 10, 1)
        t.map(4, 20, 2)
        t.map(4, 30, 3)
        self.assertEqual(t.walk(4, 3), 30)

    def test_pages_are_independent(self):
        t = make_table()
        t.map(1, 100, 1)
        t.map(2, 200, 1)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertEqual(t.walk(2, 1), 200)

    def test_remap_same_version_same_frame_is_idempotent(self):
        t = make_table()
        t.map(1, 100, 3)
        t.map(1, 100, 3)
        self.assertEqual(t.walk(1, 3), 100)

    def test_same_frame_can_back_multiple_pages(self):
        t = make_table()
        t.map(1, 100, 1)
        t.map(2, 100, 1)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertEqual(t.walk(2, 1), 100)


class TestUnmap(unittest.TestCase):
    def test_unmap_unknown_page_returns_false(self):
        t = make_table()
        self.assertFalse(t.unmap(9))

    def test_unmap_mapped_page_returns_true(self):
        t = make_table()
        t.map(1, 100, 1)
        self.assertTrue(t.unmap(1))

    def test_walk_after_unmap_is_none_at_current_version(self):
        t = make_table()
        t.map(1, 100, 1)
        t.unmap(1)
        self.assertIsNone(t.walk(1, t.version()))

    def test_unmap_twice_returns_false(self):
        t = make_table()
        t.map(1, 100, 1)
        self.assertTrue(t.unmap(1))
        self.assertFalse(t.unmap(1))

    def test_unmap_leaves_other_pages_alone(self):
        t = make_table()
        t.map(1, 100, 1)
        t.map(2, 200, 1)
        t.unmap(1)
        self.assertIsNone(t.walk(1, t.version()))
        self.assertEqual(t.walk(2, 1), 200)


class TestRollback(unittest.TestCase):
    def test_rollback_to_current_version_is_noop(self):
        t = make_table()
        t.map(1, 100, 1)
        t.map(1, 200, 2)
        t.rollback(2)
        self.assertEqual(t.walk(1, 2), 200)

    def test_rollback_drops_pages_mapped_only_later(self):
        t = make_table()
        t.map(1, 100, 1)
        t.map(2, 200, 5)
        t.rollback(2)
        self.assertEqual(t.walk(1, 2), 100)
        self.assertIsNone(t.walk(2, 5))

    def test_rollback_below_all_mappings_unmaps(self):
        t = make_table()
        t.map(1, 100, 5)
        t.rollback(0)
        self.assertIsNone(t.walk(1, 5))


class TestVersion(unittest.TestCase):
    def test_version_starts_at_zero(self):
        t = make_table()
        self.assertEqual(t.version(), 0)

    def test_map_advances_version(self):
        t = make_table()
        t.map(1, 100, 3)
        self.assertEqual(t.version(), 3)

    def test_version_never_goes_backwards_on_map(self):
        t = make_table()
        t.map(1, 100, 3)
        t.map(2, 200, 2)
        self.assertEqual(t.version(), 3)

    def test_rollback_pulls_version_back(self):
        t = make_table()
        t.map(1, 100, 5)
        t.rollback(2)
        self.assertEqual(t.version(), 2)


class TestConcurrencySafety(unittest.TestCase):
    def test_distinct_pages_from_many_threads(self):
        t = make_table()

        def worker(page):
            for ver in range(1, 6):
                t.map(page, page * 10, ver)

        threads = [threading.Thread(target=worker, args=(p,)) for p in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        for p in range(8):
            self.assertEqual(t.walk(p, 5), p * 10)


if __name__ == "__main__":
    unittest.main()
