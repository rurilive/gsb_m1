"""写入端的既有行为锁定：append/close 语义与文件骨架。"""

import json
import os
import struct
import tempfile
import unittest

from colpage.errors import SchemaError
from colpage.reader import ColumnFile
from colpage.schema import Schema
from colpage.store import MAGIC, ColumnStore, write_file


SCHEMA = Schema([("id", "int"), ("city", "str")])
ROWS = [{"id": 1, "city": "北京"}, {"id": 2, "city": "上海"}]


class StoreTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)

    def tearDown(self):
        os.unlink(self.path)

    def raw(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def footer(self):
        data = self.raw()
        size = struct.unpack("<I", data[-4:])[0]
        return json.loads(data[len(data) - 4 - size:len(data) - 4].decode("utf-8"))

    def test_write_file_returns_row_count(self):
        self.assertEqual(write_file(self.path, SCHEMA, ROWS), 2)
        self.assertTrue(self.raw().startswith(MAGIC))
        footer = self.footer()
        self.assertEqual(footer["rows"], 2)
        self.assertEqual([column["name"] for column in footer["columns"]],
                         ["id", "city"])
        self.assertEqual([column["kind"] for column in footer["columns"]],
                         ["int", "str"])

    def test_incremental_append_and_close(self):
        store = ColumnStore(self.path, SCHEMA)
        self.assertEqual(store.row_count, 0)
        self.assertFalse(store.closed)
        for row in ROWS:
            store.append(row)
        self.assertEqual(store.row_count, 2)
        store.close()
        self.assertTrue(store.closed)
        self.assertEqual(self.footer()["rows"], 2)

    def test_append_rejects_bad_row(self):
        store = ColumnStore(self.path, SCHEMA)
        store.append(ROWS[0])
        with self.assertRaises(SchemaError):
            store.append({"id": "1", "city": "北京"})
        with self.assertRaises(SchemaError):
            store.append({"id": 1})
        self.assertEqual(store.row_count, 1)
        store.close()

    def test_append_after_close_rejected(self):
        store = ColumnStore(self.path, SCHEMA)
        with store:
            store.append(ROWS[0])
        with self.assertRaises(ValueError):
            store.append(ROWS[1])

    def test_close_is_idempotent(self):
        store = ColumnStore(self.path, SCHEMA)
        store.append(ROWS[0])
        store.close()
        first = self.raw()
        store.close()
        self.assertEqual(self.raw(), first)

    def test_context_manager_closes(self):
        with ColumnStore(self.path, SCHEMA) as store:
            store.append(ROWS[0])
        self.assertTrue(store.closed)
        self.assertEqual(self.footer()["rows"], 1)

    def test_empty_table(self):
        self.assertEqual(write_file(self.path, SCHEMA, []), 0)
        self.assertEqual(self.footer()["rows"], 0)

    def test_row_is_snapshotted_on_append(self):
        row = {"id": 9, "city": "北京"}
        store = ColumnStore(self.path, SCHEMA)
        store.append(row)
        row["id"] = 999
        store.close()
        self.assertEqual(ColumnFile(self.path).read_row(0), {"id": 9, "city": "北京"})

    def test_bad_schema_rejected(self):
        with self.assertRaises(SchemaError):
            ColumnStore(self.path, [("id", "int")])


if __name__ == "__main__":
    unittest.main()
