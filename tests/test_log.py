"""LocalLog 现有行为的锁定测试：追加、按序号读回、截断与空日志语义。

只覆盖当前实现已经具备的能力。主从复制、日志匹配、多数提交、任期与选举、
崩溃恢复都还没有，新增行为另建测试文件，不改动本文件。
"""

import unittest

from replog import Entry, InvalidIndex, LocalLog


class TestAppend(unittest.TestCase):
    def test_append_returns_index(self):
        log = LocalLog()
        self.assertEqual(log.append(term=1, command="a"), 1)

    def test_append_assigns_contiguous_indexes(self):
        log = LocalLog()
        self.assertEqual(log.append(term=1, command="a"), 1)
        self.assertEqual(log.append(term=1, command="b"), 2)
        self.assertEqual(log.append(term=2, command="c"), 3)

    def test_entries_keep_insertion_order(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=2, command="b")
        self.assertEqual([e.command for e in log.entries()], ["a", "b"])

    def test_entries_returns_a_copy(self):
        log = LocalLog()
        log.append(term=1, command="a")
        snapshot = log.entries()
        snapshot.clear()
        self.assertEqual(log.size(), 1)

    def test_empty_log_has_no_entries(self):
        self.assertEqual(LocalLog().entries(), [])


class TestByIndexRead(unittest.TestCase):
    def test_get_returns_entry(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=3, command="b")
        entry = log.get(2)
        self.assertIsInstance(entry, Entry)
        self.assertEqual(entry.index, 2)
        self.assertEqual(entry.term, 3)
        self.assertEqual(entry.command, "b")

    def test_size_matches_entry_count(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=1, command="b")
        self.assertEqual(log.size(), 2)

    def test_last_index_grows_with_append(self):
        log = LocalLog()
        self.assertEqual(log.last_index(), 0)
        log.append(term=1, command="a")
        self.assertEqual(log.last_index(), 1)

    def test_last_term_is_zero_for_empty_log(self):
        self.assertEqual(LocalLog().last_term(), 0)

    def test_last_term_tracks_most_recent(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=5, command="b")
        self.assertEqual(log.last_term(), 5)

    def test_term_at_returns_entry_term(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=3, command="b")
        self.assertEqual(log.term_at(2), 3)


class TestTruncate(unittest.TestCase):
    def test_truncate_from_drops_index_and_after(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=1, command="b")
        log.append(term=1, command="c")
        dropped = log.truncate_from(2)
        self.assertEqual([e.command for e in dropped], ["b", "c"])
        self.assertEqual([e.command for e in log.entries()], ["a"])

    def test_truncate_at_end_is_a_noop(self):
        log = LocalLog()
        log.append(term=1, command="a")
        dropped = log.truncate_from(2)
        self.assertEqual(dropped, [])
        self.assertEqual(log.size(), 1)

    def test_truncate_whole_log(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.truncate_from(1)
        self.assertEqual(log.entries(), [])
        self.assertEqual(log.last_index(), 0)


class TestCommitIndex(unittest.TestCase):
    def test_commit_index_starts_at_zero(self):
        self.assertEqual(LocalLog().commit_index(), 0)

    def test_truncate_pulls_commit_index_back(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.append(term=1, command="b")
        log._commit_index = 2
        log.truncate_from(2)
        self.assertEqual(log.commit_index(), 1)


class TestReset(unittest.TestCase):
    def test_reset_clears_entries(self):
        log = LocalLog()
        log.append(term=1, command="a")
        log.reset()
        self.assertEqual(log.entries(), [])
        self.assertEqual(log.commit_index(), 0)


class TestIndexValidation(unittest.TestCase):
    def test_term_at_zero_rejected(self):
        with self.assertRaises(InvalidIndex):
            LocalLog().term_at(0)

    def test_term_at_beyond_end_rejected(self):
        log = LocalLog()
        log.append(term=1, command="a")
        with self.assertRaises(InvalidIndex):
            log.term_at(2)

    def test_get_beyond_end_rejected(self):
        log = LocalLog()
        log.append(term=1, command="a")
        with self.assertRaises(InvalidIndex):
            log.get(2)

    def test_truncate_negative_rejected(self):
        with self.assertRaises(InvalidIndex):
            LocalLog().truncate_from(-1)

    def test_non_integer_index_rejected(self):
        log = LocalLog()
        log.append(term=1, command="a")
        with self.assertRaises(InvalidIndex):
            log.term_at(1.5)

    def test_bool_index_rejected(self):
        with self.assertRaises(InvalidIndex):
            LocalLog().term_at(True)

    def test_truncate_beyond_end_plus_one_rejected(self):
        log = LocalLog()
        log.append(term=1, command="a")
        with self.assertRaises(InvalidIndex):
            log.truncate_from(3)

    def test_all_errors_share_common_base(self):
        from replog import RepLogError

        self.assertTrue(issubclass(InvalidIndex, RepLogError))

    def test_rejected_term_at_leaves_log_untouched(self):
        log = LocalLog()
        log.append(term=1, command="a")
        try:
            log.term_at(5)
        except InvalidIndex:
            pass
        self.assertEqual(log.size(), 1)


if __name__ == "__main__":
    unittest.main()
