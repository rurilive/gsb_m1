"""版本化语义的回归测试：回溯取值、取消记账、回滚口径、冲突判定。

不改动 tests/test_page.py 的行为基线，这里锁定修复后的新行为。
"""

import threading
import unittest

from vecpage import MappingConflict, PageTable


class TestVersionedWalk(unittest.TestCase):
    def test_walk_returns_frame_as_of_requested_version(self):
        t = PageTable()
        t.map(7, 100, 1)
        t.map(7, 200, 2)
        self.assertEqual(t.walk(7, 1), 100)
        self.assertEqual(t.walk(7, 2), 200)

    def test_walk_before_first_mapping_is_none(self):
        t = PageTable()
        t.map(7, 100, 3)
        self.assertIsNone(t.walk(7, 2))

    def test_walk_between_versions_uses_latest_earlier_entry(self):
        t = PageTable()
        t.map(7, 100, 1)
        t.map(7, 200, 5)
        self.assertEqual(t.walk(7, 4), 100)


class TestUnmapKeepsHistory(unittest.TestCase):
    def test_history_survives_unmap(self):
        t = PageTable()
        t.map(9, 300, 1)
        t.map(9, 301, 2)
        t.unmap(9)
        self.assertEqual(t.walk(9, 1), 300)
        self.assertEqual(t.walk(9, 2), 301)

    def test_unmap_takes_effect_from_new_version(self):
        t = PageTable()
        t.map(9, 300, 1)
        t.unmap(9)
        self.assertIsNone(t.walk(9, t.version()))
        self.assertGreater(t.version(), 1)

    def test_remap_after_unmap(self):
        t = PageTable()
        t.map(9, 300, 1)
        t.unmap(9)
        t.map(9, 400, t.version() + 1)
        self.assertEqual(t.walk(9, t.version()), 400)
        self.assertEqual(t.walk(9, 1), 300)


class TestRollbackSemantics(unittest.TestCase):
    def test_rollback_restores_frame_at_target_version(self):
        t = PageTable()
        t.map(3, 10, 1)
        t.map(3, 20, 2)
        t.rollback(1)
        self.assertEqual(t.walk(3, 1), 10)
        self.assertEqual(t.walk(3, t.version()), 10)

    def test_rollback_restores_unmapped_state(self):
        t = PageTable()
        t.map(3, 10, 1)
        t.unmap(3)
        t.rollback(1)
        self.assertEqual(t.walk(3, t.version()), 10)

    def test_rollback_drops_later_mappings(self):
        t = PageTable()
        t.map(3, 10, 1)
        t.map(3, 20, 2)
        t.rollback(1)
        # 版本 2 的记录被丢掉，之后任意版本翻页都回溯到回滚点的帧
        self.assertEqual(t.walk(3, 2), 10)


class TestMappingConflict(unittest.TestCase):
    def test_same_page_same_version_different_frame_conflicts(self):
        t = PageTable()
        t.map(5, 40, 4)
        with self.assertRaises(MappingConflict):
            t.map(5, 41, 4)

    def test_same_page_same_version_same_frame_is_fine(self):
        t = PageTable()
        t.map(5, 40, 4)
        t.map(5, 40, 4)
        self.assertEqual(t.walk(5, 4), 40)

    def test_same_page_different_version_is_fine(self):
        t = PageTable()
        t.map(5, 40, 4)
        t.map(5, 41, 5)
        self.assertEqual(t.walk(5, 5), 41)

    def test_concurrent_conflicting_writers_exactly_one_wins(self):
        t = PageTable()
        barrier = threading.Barrier(2)
        outcomes = []
        guard = threading.Lock()

        def writer(frame):
            barrier.wait()
            try:
                t.map(5, frame, 4)
                outcome = "accepted"
            except MappingConflict:
                outcome = "conflict"
            with guard:
                outcomes.append(outcome)

        threads = [threading.Thread(target=writer, args=(f,)) for f in (40, 41)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(outcomes.count("accepted"), 1)
        self.assertEqual(outcomes.count("conflict"), 1)
        self.assertIn(t.walk(5, 4), (40, 41))


if __name__ == "__main__":
    unittest.main()
