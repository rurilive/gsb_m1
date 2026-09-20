"""追加型文件存储的锁定测试。"""

import os
import shutil
import tempfile
import unittest

from auditchain.store import CorruptLogError, RecordStore


class StoreTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="auditchain-store-")
        self.path = os.path.join(self.tmpdir, "audit.log")
        self.store = RecordStore(self.path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def write_raw(self, blob):
        with open(self.path, "ab") as handle:
            handle.write(blob)


class TestScan(StoreTestBase):
    def test_missing_file_scans_empty(self):
        self.assertEqual(self.store.scan(), ([], 0))
        self.assertEqual(self.store.size(), 0)

    def test_entries_carry_byte_offsets_in_order(self):
        self.store.append({"seq": 1})
        self.store.append({"seq": 2})
        entries, valid_end = self.store.scan()
        self.assertEqual([offset for offset, _ in entries], [0, 10])
        self.assertEqual([record["seq"] for _, record in entries], [1, 2])
        self.assertEqual(valid_end, 20)
        self.assertEqual(self.store.size(), 20)

    def test_append_returns_new_size(self):
        self.assertEqual(self.store.append({"seq": 1}), 10)

    def test_reopen_keeps_accumulating(self):
        self.store.append({"seq": 1})
        again = RecordStore(self.path)
        again.append({"seq": 2})
        entries, _ = again.scan()
        self.assertEqual([record["seq"] for _, record in entries], [1, 2])


class TestTornTail(StoreTestBase):
    def test_half_written_tail_is_skipped(self):
        self.store.append({"seq": 1})
        self.write_raw(b'{"seq":2,"act')
        entries, valid_end = self.store.scan()
        self.assertEqual([record["seq"] for _, record in entries], [1])
        self.assertEqual(valid_end, 10)
        self.assertEqual(self.store.size(), 23)

    def test_torn_tail_after_complete_records_is_skipped(self):
        self.store.append({"seq": 1})
        self.store.append({"seq": 2})
        self.write_raw(b'{"seq":3}')
        entries, valid_end = self.store.scan()
        self.assertEqual(len(entries), 2)
        self.assertEqual(valid_end, 20)

    def test_truncate_drops_the_torn_tail(self):
        self.store.append({"seq": 1})
        self.write_raw(b'{"seq":2,"act')
        _, valid_end = self.store.scan()
        self.store.truncate(valid_end)
        self.assertEqual(self.store.size(), 10)
        self.assertEqual(self.store.append({"seq": 2}), 20)
        entries, _ = self.store.scan()
        self.assertEqual([record["seq"] for _, record in entries], [1, 2])


class TestCorruption(StoreTestBase):
    def test_garbage_line_in_the_middle_raises(self):
        self.store.append({"seq": 1})
        self.write_raw(b"not a record\n")
        self.store.append({"seq": 2})
        with self.assertRaises(CorruptLogError) as caught:
            self.store.scan()
        self.assertEqual(caught.exception.offset, 10)

    def test_garbage_is_not_swallowed_by_a_later_append(self):
        self.write_raw(b'{"seq":1}\n["nope"]\n')
        self.store.append({"seq": 2})
        with self.assertRaises(CorruptLogError):
            self.store.scan()


if __name__ == "__main__":
    unittest.main()
