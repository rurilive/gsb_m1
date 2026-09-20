"""四个修复点的验收测试（基线之外另开的文件）。"""

import threading
import unittest

from vecpage import MappingConflict, PageTable


class TestWalkByVersion(unittest.TestCase):
    def test_old_version_reads_old_frame(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.map(1, 200, 2)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertEqual(t.walk(1, 2), 200)

    def test_frame_persists_until_superseded(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.map(1, 200, 4)
        for ver in (1, 2, 3):
            self.assertEqual(t.walk(1, ver), 100)
        for ver in (4, 5, 9):
            self.assertEqual(t.walk(1, ver), 200)

    def test_walk_before_first_mapping_is_none(self):
        t = PageTable()
        t.map(1, 100, 5)
        self.assertIsNone(t.walk(1, 1))
        self.assertEqual(t.walk(1, 5), 100)

    def test_late_arriving_old_version_entry_is_kept_in_order(self):
        t = PageTable()
        t.map(1, 200, 3)
        t.map(1, 100, 1)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertEqual(t.walk(1, 2), 100)
        self.assertEqual(t.walk(1, 3), 200)


class TestUnmapKeepsHistory(unittest.TestCase):
    def test_unmap_only_takes_effect_from_new_version(self):
        t = PageTable()
        t.map(9, 300, 1)
        t.map(9, 301, 2)
        self.assertTrue(t.unmap(9))
        self.assertEqual(t.version(), 3)
        self.assertIsNone(t.walk(9, t.version()))
        self.assertEqual(t.walk(9, 1), 300)
        self.assertEqual(t.walk(9, 2), 301)

    def test_remap_after_unmap_does_not_restore_old_versions(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.unmap(1)
        t.map(1, 400, t.version() + 1)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertIsNone(t.walk(1, 2))
        self.assertEqual(t.walk(1, 3), 400)

    def test_unmap_then_unmap_again_is_false(self):
        t = PageTable()
        t.map(1, 100, 1)
        self.assertTrue(t.unmap(1))
        self.assertFalse(t.unmap(1))

    def test_unmap_advances_version_even_with_explicit_later_versions(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.map(2, 200, 8)
        self.assertTrue(t.unmap(1))
        self.assertEqual(t.version(), 9)
        self.assertIsNone(t.walk(1, 9))
        self.assertEqual(t.walk(1, 8), 100)


class TestRollbackSemantics(unittest.TestCase):
    def test_rollback_restores_frame_at_rollback_point(self):
        t = PageTable()
        t.map(3, 10, 1)
        t.map(3, 20, 2)
        t.rollback(1)
        self.assertEqual(t.walk(3, 1), 10)

    def test_rollback_discards_later_remap_even_when_reading_new_version(self):
        t = PageTable()
        t.map(3, 10, 1)
        t.map(3, 20, 2)
        t.rollback(1)
        self.assertEqual(t.walk(3, 2), 10)

    def test_rollback_discards_unmap_done_later(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.unmap(1)
        t.rollback(1)
        self.assertEqual(t.walk(1, 1), 100)

    def test_rollback_to_point_where_page_was_unmapped_stays_none(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.unmap(1)
        t.map(1, 500, 4)
        t.rollback(2)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertIsNone(t.walk(1, 2))

    def test_rollback_can_be_remapped_afterwards(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.map(1, 200, 2)
        t.rollback(1)
        t.map(1, 300, 3)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertEqual(t.walk(1, 2), 100)
        self.assertEqual(t.walk(1, 3), 300)


class TestConflictDetection(unittest.TestCase):
    def test_same_page_same_version_different_frames_conflicts(self):
        t = PageTable()
        t.map(1, 100, 2)
        with self.assertRaises(MappingConflict):
            t.map(1, 200, 2)
        self.assertEqual(t.walk(1, 2), 100)

    def test_same_frame_remap_same_version_is_not_conflict(self):
        t = PageTable()
        t.map(1, 100, 2)
        t.map(1, 100, 2)
        self.assertEqual(t.walk(1, 2), 100)

    def test_different_versions_are_not_conflict(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.map(1, 200, 2)
        self.assertEqual(t.walk(1, 1), 100)
        self.assertEqual(t.walk(1, 2), 200)

    def test_remap_onto_tombstone_same_version_conflicts(self):
        t = PageTable()
        t.map(1, 100, 1)
        t.unmap(1)
        with self.assertRaises(MappingConflict):
            t.map(1, 200, 2)
        self.assertIsNone(t.walk(1, 2))

    def test_concurrent_same_version_different_frames_one_wins(self):
        t = PageTable()
        barrier = threading.Barrier(8)
        outcomes = []
        guard = threading.Lock()

        def writer(frame):
            barrier.wait()
            try:
                t.map(5, frame, 4)
                result = "accepted"
            except MappingConflict:
                result = "conflict"
            with guard:
                outcomes.append(result)

        threads = [
            threading.Thread(target=writer, args=(40 + i,)) for i in range(8)
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(outcomes.count("accepted"), 1)
        self.assertEqual(outcomes.count("conflict"), 7)
        self.assertIn(t.walk(5, 4), [40 + i for i in range(8)])

    def test_concurrent_same_version_same_frame_all_accepted(self):
        t = PageTable()
        barrier = threading.Barrier(8)
        errors = []
        guard = threading.Lock()

        def writer():
            barrier.wait()
            try:
                t.map(6, 77, 4)
            except MappingConflict as exc:
                with guard:
                    errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(errors, [])
        self.assertEqual(t.walk(6, 4), 77)


if __name__ == "__main__":
    unittest.main()
