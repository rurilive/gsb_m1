"""TsStore 现有行为的锁定测试。"""

import os
import struct
import tempfile
import unittest

from tstore import TsStore
from tstore.errors import OutOfOrderError, TsFormatError

#: 老格式文件的原样字节：魔数头加三条裸记录。
LEGACY_RAW = (
    b"TSRAW01\n"
    + struct.pack("<qd", 100, 1.5)
    + struct.pack("<qd", 100, 2.5)
    + struct.pack("<qd", 105, 3.5)
)


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "points.ts")

    def make_store(self, path=None):
        store = TsStore(path or self.path)
        self.addCleanup(store.close)
        return store

    def write_pair_file(self, raw, name="legacy.ts"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "wb") as fh:
            fh.write(raw)
        return path


class TestAppend(StoreCase):
    def test_new_file_starts_empty(self):
        s = self.make_store()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.read_all(), [])
        self.assertIsNone(s.last_ts)

    def test_append_then_len(self):
        s = self.make_store()
        s.append(10, 1.0)
        s.append(20, 2.0)
        self.assertEqual(len(s), 2)

    def test_pairs_read_back_in_order(self):
        s = self.make_store()
        s.append(10, 1.0)
        s.append(20, 2.0)
        s.append(20, 2.5)
        self.assertEqual(s.read_all(), [(10, 1.0), (20, 2.0), (20, 2.5)])

    def test_equal_timestamps_accepted(self):
        s = self.make_store()
        s.append(7, 1.0)
        s.append(7, 2.0)
        self.assertEqual(len(s), 2)

    def test_negative_timestamp_accepted(self):
        s = self.make_store()
        s.append(-5, 1.0)
        s.append(-5, 2.0)
        s.append(0, 3.0)
        self.assertEqual(s.last_ts, 0)

    def test_out_of_order_rejected(self):
        s = self.make_store()
        s.append(10, 1.0)
        with self.assertRaises(OutOfOrderError):
            s.append(9, 2.0)

    def test_rejected_append_leaves_store_intact(self):
        s = self.make_store()
        s.append(10, 1.0)
        with self.assertRaises(OutOfOrderError):
            s.append(9, 99.0)
        self.assertEqual(len(s), 1)
        self.assertEqual(s.read_all(), [(10, 1.0)])
        self.assertEqual(s.last_ts, 10)

    def test_timestamp_must_be_int(self):
        s = self.make_store()
        for bad in ("10", 10.0, None, True):
            with self.assertRaises(TypeError):
                s.append(bad, 1.0)

    def test_value_must_be_number(self):
        s = self.make_store()
        for bad in ("1.0", None, [1.0], True):
            with self.assertRaises(TypeError):
                s.append(1, bad)

    def test_int_value_accepted(self):
        s = self.make_store()
        s.append(1, 3)
        self.assertEqual(s.read_all(), [(1, 3)])


class TestAppendMany(StoreCase):
    def test_batch_written_in_order(self):
        s = self.make_store()
        s.append_many([(1, 1.0), (2, 2.0), (4, 4.0)])
        self.assertEqual(s.read_all(), [(1, 1.0), (2, 2.0), (4, 4.0)])

    def test_batch_accepts_duplicates(self):
        s = self.make_store()
        s.append_many([(1, 1.0), (1, 2.0), (1, 3.0)])
        self.assertEqual(len(s), 3)

    def test_batch_accepts_generator(self):
        s = self.make_store()
        s.append_many((pair for pair in [(1, 1.0), (2, 2.0)]))
        self.assertEqual(len(s), 2)

    def test_batch_checked_against_existing_last_ts(self):
        s = self.make_store()
        s.append(5, 5.0)
        with self.assertRaises(OutOfOrderError):
            s.append_many([(5, 6.0), (4, 7.0)])
        self.assertEqual(len(s), 1)

    def test_batch_rejected_atomically(self):
        s = self.make_store()
        s.append(5, 5.0)
        with self.assertRaises(OutOfOrderError):
            s.append_many([(6, 6.0), (7, 7.0), (6, 8.0)])
        self.assertEqual(s.read_all(), [(5, 5.0)])
        self.assertEqual(s.last_ts, 5)
        with self.assertRaises(OutOfOrderError):
            s.append(4, 4.0)

    def test_bad_type_inside_batch_rejected_atomically(self):
        s = self.make_store()
        with self.assertRaises(TypeError):
            s.append_many([(1, 1.0), (2, "x")])
        self.assertEqual(len(s), 0)


class TestRead(StoreCase):
    def fill(self, pairs=None):
        s = self.make_store()
        s.append_many(pairs or [(10, 1.0), (20, 2.0), (20, 2.5), (40, 4.0)])
        return s

    def test_read_at_first_and_last(self):
        s = self.fill()
        self.assertEqual(s.read_at(0), (10, 1.0))
        self.assertEqual(s.read_at(3), (40, 4.0))

    def test_read_at_negative_index(self):
        s = self.fill()
        self.assertEqual(s.read_at(-1), (40, 4.0))
        self.assertEqual(s.read_at(-4), (10, 1.0))

    def test_read_at_out_of_range(self):
        s = self.fill()
        for bad in (4, -5, 100):
            with self.assertRaises(IndexError):
                s.read_at(bad)

    def test_read_at_on_empty_store(self):
        s = self.make_store()
        with self.assertRaises(IndexError):
            s.read_at(0)

    def test_find_exact_timestamp(self):
        s = self.fill()
        self.assertEqual(s.find(20), 1)

    def test_find_between_timestamps(self):
        s = self.fill()
        self.assertEqual(s.find(11), 1)

    def test_find_duplicates_returns_earliest(self):
        s = self.fill()
        self.assertEqual(s.find(20), 1)
        self.assertEqual(s.read_at(s.find(20)), (20, 2.0))

    def test_find_before_first_returns_zero(self):
        s = self.fill()
        self.assertEqual(s.find(0), 0)
        self.assertEqual(s.find(10), 0)

    def test_find_past_end_returns_minus_one(self):
        s = self.fill()
        self.assertEqual(s.find(41), -1)

    def test_find_on_empty_store(self):
        s = self.make_store()
        self.assertEqual(s.find(0), -1)

    def test_iteration_is_ordered(self):
        s = self.fill()
        self.assertEqual(list(s), [(10, 1.0), (20, 2.0), (20, 2.5), (40, 4.0)])

    def test_read_all_returns_fresh_list(self):
        s = self.fill()
        out = s.read_all()
        out.append((99, 9.9))
        self.assertEqual(len(s), 4)


class TestSessions(StoreCase):
    def test_same_handle_sees_records_just_appended(self):
        s = self.make_store()
        s.append(1, 1.0)
        s.append(2, 2.0)
        self.assertEqual(len(s), 2)
        self.assertEqual(s.read_all(), [(1, 1.0), (2, 2.0)])
        self.assertEqual(s.read_at(1), (2, 2.0))
        self.assertEqual(s.find(2), 1)

    def test_close_and_reopen_sees_everything(self):
        s = self.make_store()
        s.append_many([(1, 1.0), (2, 2.0)])
        s.close()
        again = TsStore(self.path)
        self.addCleanup(again.close)
        self.assertEqual(again.read_all(), [(1, 1.0), (2, 2.0)])
        self.assertEqual(again.last_ts, 2)

    def test_append_after_reopen_continues(self):
        s = self.make_store()
        s.append(1, 1.0)
        s.close()
        s2 = TsStore(self.path)
        self.addCleanup(s2.close)
        s2.append(2, 2.0)
        with self.assertRaises(OutOfOrderError):
            s2.append(0, 0.0)
        s2.close()
        s3 = TsStore(self.path)
        self.addCleanup(s3.close)
        self.assertEqual(s3.read_all(), [(1, 1.0), (2, 2.0)])
        self.assertEqual(len(s3), 2)

    def test_close_is_idempotent(self):
        s = self.make_store()
        s.append(1, 1.0)
        s.close()
        s.close()

    def test_context_manager_flushes_on_exit(self):
        with TsStore(self.path) as s:
            s.append(1, 1.0)
        again = TsStore(self.path)
        self.addCleanup(again.close)
        self.assertEqual(again.read_all(), [(1, 1.0)])

    def test_empty_file_is_initialized(self):
        open(self.path, "wb").close()
        s = self.make_store()
        s.append(1, 1.0)
        self.assertEqual(s.read_all(), [(1, 1.0)])


class TestStats(StoreCase):
    def test_counters(self):
        s = self.make_store()
        s.append(1, 1.0)
        s.append_many([(2, 2.0), (3, 3.0)])
        s.read_at(0)
        s.read_all()
        st = s.stats()
        self.assertEqual(st["records"], 3)
        self.assertEqual(st["appends"], 3)
        self.assertEqual(st["reads"], 4)

    def test_stats_returns_fresh_dict(self):
        s = self.make_store()
        st = s.stats()
        st["records"] = 99
        self.assertEqual(s.stats()["records"], 0)

    def test_bytes_on_disk_is_positive_int(self):
        s = self.make_store()
        s.append_many([(1, 1.0), (2, 2.0)])
        self.assertIsInstance(s.stats()["bytes_on_disk"], int)
        self.assertGreater(s.stats()["bytes_on_disk"], 0)


class TestFormatErrors(StoreCase):
    def test_unknown_magic_rejected(self):
        path = self.write_pair_file(b"NOTAMAG\n" + b"\x00" * 16)
        with self.assertRaises(TsFormatError):
            TsStore(path)

    def test_ragged_length_rejected(self):
        path = self.write_pair_file(b"TSRAW01\n" + b"\x00" * 20)
        with self.assertRaises(TsFormatError):
            TsStore(path)


class TestLegacyFiles(StoreCase):
    def open_legacy(self):
        path = self.write_pair_file(LEGACY_RAW)
        store = TsStore(path)
        self.addCleanup(store.close)
        return store, path

    def test_reads_legacy_raw_file(self):
        s, _ = self.open_legacy()
        self.assertEqual(len(s), 3)
        self.assertEqual(s.read_all(), [(100, 1.5), (100, 2.5), (105, 3.5)])

    def test_legacy_random_access_and_find(self):
        s, _ = self.open_legacy()
        self.assertEqual(s.read_at(2), (105, 3.5))
        self.assertEqual(s.read_at(-1), (105, 3.5))
        self.assertEqual(s.find(100), 0)
        self.assertEqual(s.find(101), 2)
        self.assertEqual(s.find(106), -1)

    def test_append_to_legacy_file_then_reread(self):
        s, path = self.open_legacy()
        s.append(200, 9.5)
        self.assertEqual(len(s), 4)
        self.assertEqual(s.read_at(-1), (200, 9.5))
        s.close()
        again = TsStore(path)
        self.addCleanup(again.close)
        self.assertEqual(
            again.read_all(), [(100, 1.5), (100, 2.5), (105, 3.5), (200, 9.5)]
        )
        self.assertEqual(again.find(150), 3)
        with self.assertRaises(OutOfOrderError):
            again.append(199, 0.5)


if __name__ == "__main__":
    unittest.main()
