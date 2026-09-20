"""spillkit 现有行为的锁定测试。

覆盖内存内直排、run 文件读写、句柄预算和收尾清理这些已经确定的行为，
这些行为在修复过程中不允许改动。
"""

import os
import shutil
import tempfile
import unittest

from spillkit import SortDeduper, sort_dedup
from spillkit.runfile import RunFileGuard, RunReader, TooManyOpenRuns, write_run


def rec(key, payload):
    """拼一条 制表符 分隔的记录。"""
    return "%s\t%s" % (key, payload)


class TestInMemoryPath(unittest.TestCase):
    """数据装得下时不出盘，行为要一直保持。"""

    def test_sorted_by_key(self):
        out = sort_dedup(
            [rec("c", "3"), rec("a", "1"), rec("b", "2")], memory_limit=16
        )
        self.assertEqual(out, [rec("a", "1"), rec("b", "2"), rec("c", "3")])

    def test_dedup_keeps_first_occurrence(self):
        out = sort_dedup(
            [rec("a", "first"), rec("b", "x"), rec("a", "second")], memory_limit=16
        )
        self.assertEqual(out, [rec("a", "first"), rec("b", "x")])

    def test_empty_input(self):
        self.assertEqual(sort_dedup([], memory_limit=4), [])

    def test_custom_key(self):
        records = ["x,3", "y,1", "z,2"]
        out = sort_dedup(records, memory_limit=8, key=lambda r: r.split(",")[1])
        self.assertEqual(out, ["y,1", "z,2", "x,3"])

    def test_all_in_memory_means_no_spill(self):
        sorter = SortDeduper(memory_limit=100)
        try:
            for i in range(5):
                sorter.add(rec("k%d" % i, "v"))
            sorter.finish()
            stats = sorter.stats()
            self.assertEqual(stats["records_in"], 5)
            self.assertEqual(stats["runs_written"], 0)
            self.assertLessEqual(stats["peak_buffered"], 100)
        finally:
            sorter.close()


class TestSpillPath(unittest.TestCase):
    """恰好装满整数倍的缓冲会走落盘归并，行为锁定。"""

    def test_exact_multiple_of_limit(self):
        records = [rec("k%02d" % i, "v%d" % i) for i in range(10)]
        shuffled = records[6:] + records[:6]
        sorter = SortDeduper(memory_limit=5, fd_limit=8)
        try:
            for record in shuffled:
                sorter.add(record)
            out = sorter.finish()
            self.assertEqual(out, records)
            self.assertEqual(sorter.stats()["runs_written"], 2)
            self.assertLessEqual(sorter.stats()["peak_buffered"], 5)
        finally:
            sorter.close()


class TestRunFile(unittest.TestCase):
    """run 文件的编码与句柄预算。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="spillkit-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_roundtrip_special_characters(self):
        guard = RunFileGuard(3)
        path = os.path.join(self.dir, "r.run")
        entries = [(1, rec("键一", "值 含空格")), (2, rec("k", "a\"b\\c"))]
        write_run(path, entries, guard)
        reader = RunReader(path, guard)
        try:
            got = []
            while True:
                item = reader.next()
                if item is None:
                    break
                got.append(item)
        finally:
            reader.close()
        self.assertEqual(got, entries)
        self.assertEqual(guard.open_count, 0)

    def test_guard_rejects_over_limit(self):
        guard = RunFileGuard(3)
        guard.acquire()
        guard.acquire()
        guard.acquire()
        with self.assertRaises(TooManyOpenRuns):
            guard.acquire()
        guard.release()
        guard.acquire()

    def test_guard_requires_room_for_merge(self):
        with self.assertRaises(ValueError):
            RunFileGuard(2)


class TestLifecycle(unittest.TestCase):
    """收尾清理与状态约定。"""

    def test_close_removes_spill_files(self):
        workdir = tempfile.mkdtemp(prefix="spillkit-test-")
        try:
            sorter = SortDeduper(workdir=workdir, memory_limit=3)
            for i in range(9):
                sorter.add(rec("k%d" % i, "v"))
            sorter.finish()
            sorter.close()
            self.assertEqual(os.listdir(workdir), [])
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def test_stats_fields(self):
        sorter = SortDeduper(memory_limit=4)
        try:
            sorter.add(rec("a", "1"))
            sorter.finish()
            stats = sorter.stats()
            for field in ("records_in", "runs_written", "merge_passes",
                          "peak_buffered", "peak_open_runs"):
                self.assertIn(field, stats)
        finally:
            sorter.close()

    def test_add_after_finish_rejected(self):
        sorter = SortDeduper(memory_limit=4)
        try:
            sorter.add(rec("a", "1"))
            sorter.finish()
            with self.assertRaises(RuntimeError):
                sorter.add(rec("b", "2"))
        finally:
            sorter.close()


if __name__ == "__main__":
    unittest.main()
