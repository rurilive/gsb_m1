"""读取端的既有行为锁定：顺序读、随机读、等值过滤与坏文件处理。"""

import json
import os
import struct
import tempfile
import unittest

from colpage.errors import FormatError, SchemaError
from colpage.reader import ColumnFile
from colpage.schema import Schema
from colpage.store import MAGIC, write_file


SCHEMA = Schema([("id", "int"), ("city", "str"), ("amount", "int")])


def sample_rows():
    return [
        {"id": 3, "city": "北京", "amount": 12},
        {"id": 4, "city": "上海", "amount": -3},
        {"id": 5, "city": "北京", "amount": 0},
        {"id": 6, "city": "北京", "amount": 7},
        {"id": 7, "city": "广州", "amount": -9},
    ]


class ReaderTestBase(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        self.rows = sample_rows()
        write_file(self.path, SCHEMA, self.rows)

    def tearDown(self):
        os.unlink(self.path)

    def craft(self, body, footer):
        """按格式说明手工拼一个文件（footer 自己写）。"""
        raw = json.dumps(footer).encode("utf-8")
        with open(self.path, "wb") as out:
            out.write(MAGIC)
            out.write(body)
            out.write(raw)
            out.write(struct.pack("<I", len(raw)))


class RoundTripTest(ReaderTestBase):
    def test_read_rows_returns_every_row_in_order(self):
        self.assertEqual(ColumnFile(self.path).read_rows(), self.rows)

    def test_unicode_empty_and_extreme_values_survive(self):
        rows = [
            {"id": -(1 << 63), "city": "深圳·南山", "amount": (1 << 63) - 1},
            {"id": 0, "city": "", "amount": 0},
            {"id": 41, "city": "上海", "amount": -1},
        ]
        path = self.path + ".edge"
        write_file(path, SCHEMA, rows)
        try:
            self.assertEqual(ColumnFile(path).read_rows(), rows)
        finally:
            os.unlink(path)

    def test_read_column(self):
        reader = ColumnFile(self.path)
        self.assertEqual(reader.read_column("id"), [3, 4, 5, 6, 7])
        self.assertEqual(reader.read_column("city"),
                         ["北京", "上海", "北京", "北京", "广州"])
        with self.assertRaises(SchemaError):
            reader.read_column("nope")

    def test_empty_table(self):
        path = self.path + ".empty"
        write_file(path, SCHEMA, [])
        try:
            reader = ColumnFile(path)
            self.assertEqual(reader.read_rows(), [])
            self.assertEqual(reader.row_count, 0)
            with self.assertRaises(IndexError):
                reader.read_row(0)
        finally:
            os.unlink(path)

    def test_stats_summarizes_file(self):
        reader = ColumnFile(self.path)
        stats = reader.stats()
        self.assertEqual(stats["rows"], len(self.rows))
        self.assertEqual(stats["columns"], 3)
        self.assertEqual(stats["file_bytes"], os.path.getsize(self.path))


class RandomReadTest(ReaderTestBase):
    def test_read_row_matches_sequential(self):
        reader = ColumnFile(self.path)
        for index, row in enumerate(self.rows):
            self.assertEqual(reader.read_row(index), row)

    def test_read_row_out_of_range(self):
        reader = ColumnFile(self.path)
        for index in (len(self.rows), -1):
            with self.assertRaises(IndexError):
                reader.read_row(index)


class FilterTest(ReaderTestBase):
    def test_filter_eq_on_string_and_int_columns(self):
        reader = ColumnFile(self.path)
        hits = reader.filter_eq("city", "北京")
        self.assertEqual([row["id"] for row in hits], [3, 5, 6])
        self.assertEqual(reader.filter_eq("amount", -3), [self.rows[1]])
        self.assertEqual(reader.filter_eq("city", "杭州"), [])

    def test_filter_eq_unknown_column(self):
        with self.assertRaises(SchemaError):
            ColumnFile(self.path).filter_eq("nope", 1)


class BadFileTest(ReaderTestBase):
    def test_bad_magic_and_truncated_file(self):
        with open(self.path, "wb") as out:
            out.write(b"this is not a colpage file at all")
        with self.assertRaises(FormatError):
            ColumnFile(self.path)
        write_file(self.path, SCHEMA, self.rows)
        with open(self.path, "rb") as handle:
            head = handle.read(len(MAGIC) + 4)
        with open(self.path, "wb") as out:
            out.write(head)
        with self.assertRaises(FormatError):
            ColumnFile(self.path)

    def test_footer_claiming_more_rows_than_segments(self):
        body = struct.pack("<q", 1)
        self.craft(body, {"format": 1, "rows": 5, "columns": [
            {"name": "id", "kind": "int", "codec": "raw",
             "offset": 0, "length": len(body)}]})
        with self.assertRaises(FormatError):
            ColumnFile(self.path).read_rows()

    def test_str_segment_with_broken_length(self):
        self.craft(bytes([0x80]), {"format": 1, "rows": 1, "columns": [
            {"name": "city", "kind": "str", "codec": "raw",
             "offset": 0, "length": 1}]})
        with self.assertRaises(FormatError):
            ColumnFile(self.path).read_rows()

    def test_unknown_codec_rejected(self):
        body = struct.pack("<q", 1)
        self.craft(body, {"format": 1, "rows": 1, "columns": [
            {"name": "id", "kind": "int", "codec": "mystery",
             "offset": 0, "length": len(body)}]})
        with self.assertRaises(FormatError):
            ColumnFile(self.path).read_rows()


if __name__ == "__main__":
    unittest.main()
