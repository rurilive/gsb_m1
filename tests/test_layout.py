"""裸存布局现有行为的锁定测试。"""

import unittest

from tstore.errors import TsFormatError
from tstore.layout import (
    HEADER,
    RECORD,
    pack_record,
    record_count,
    unpack_record,
    validate_header,
)


class TestHeader(unittest.TestCase):
    def test_header_is_eight_bytes(self):
        self.assertEqual(len(HEADER), 8)

    def test_validate_header_accepts_own_magic(self):
        validate_header(HEADER)

    def test_validate_header_rejects_other(self):
        with self.assertRaises(TsFormatError):
            validate_header(b"NOTHERE\n")

    def test_validate_header_rejects_short_input(self):
        with self.assertRaises(TsFormatError):
            validate_header(b"TSR")


class TestRecord(unittest.TestCase):
    def test_record_is_sixteen_bytes(self):
        self.assertEqual(RECORD.size, 16)

    def test_round_trip(self):
        buf = pack_record(1700000000, 20.5)
        self.assertEqual(len(buf), 16)
        self.assertEqual(unpack_record(buf), (1700000000, 20.5))

    def test_negative_timestamp_and_zero_value(self):
        self.assertEqual(unpack_record(pack_record(-3, 0.0)), (-3, 0.0))

    def test_iter_unpack(self):
        buf = pack_record(1, 1.0) + pack_record(2, 2.0)
        self.assertEqual(list(RECORD.iter_unpack(buf)), [(1, 1.0), (2, 2.0)])


class TestRecordCount(unittest.TestCase):
    def test_empty_body(self):
        self.assertEqual(record_count(len(HEADER)), 0)

    def test_count_from_size(self):
        self.assertEqual(record_count(len(HEADER) + 3 * RECORD.size), 3)

    def test_ragged_body_rejected(self):
        with self.assertRaises(TsFormatError):
            record_count(len(HEADER) + 5)

    def test_file_shorter_than_header_rejected(self):
        with self.assertRaises(TsFormatError):
            record_count(4)


if __name__ == "__main__":
    unittest.main()
