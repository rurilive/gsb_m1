"""带编码页的端到端行为：对拍、跳页统计、坏页容错、旧格式、流式写入。"""

import json
import os
import random
import struct
import tempfile
import unittest

from colpage import ColumnFile, Schema, write_file
from colpage import store as store_module
from colpage.codec import decode_uvarint, encode_raw
from colpage.errors import BadPageError, SchemaError
from colpage.store import MAGIC, ColumnStore


SCHEMA = Schema([("id", "int"), ("city", "str"), ("amount", "int")])
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉"]


def naive_rows_match(rows, schema):
    """朴素参考实现：整表在内存，顺序读/随机读/等值过滤都直接扫。"""

    def read_rows():
        return [dict(row) for row in rows]

    def read_row(index):
        if index < 0 or index >= len(rows):
            raise IndexError(index)
        return dict(rows[index])

    def filter_eq(name, value):
        return [dict(row) for row in rows if row[name] == value]

    return read_rows, read_row, filter_eq


def make_rows(count, seed):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        rows.append({
            "id": 5000 + index,
            "city": CITIES[rng.randrange(len(CITIES))],
            "amount": rng.randint(-20, 20),
        })
    return rows


class PagedFileTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        self._old_page_rows = store_module.PAGE_ROWS
        store_module.PAGE_ROWS = 16

    def tearDown(self):
        store_module.PAGE_ROWS = self._old_page_rows
        if os.path.exists(self.path):
            os.unlink(self.path)

    def footer(self):
        with open(self.path, "rb") as handle:
            data = handle.read()
        size = struct.unpack("<I", data[-4:])[0]
        return json.loads(
            data[len(data) - 4 - size:len(data) - 4].decode())

    def test_footer_describes_paged_segments(self):
        rows = make_rows(40, 1)
        write_file(self.path, SCHEMA, rows)
        footer = self.footer()
        self.assertEqual(footer["format"], 2)
        for column in footer["columns"]:
            self.assertEqual(column["codec"], "paged")
            self.assertEqual(len(column["pages"]), 3)
            self.assertEqual(sum(entry[2] for entry in column["pages"]), 40)

    def test_roundtrip_many_pages(self):
        rows = make_rows(100, 2)
        write_file(self.path, SCHEMA, rows)
        self.assertEqual(ColumnFile(self.path).read_rows(), rows)
        self.assertEqual(ColumnFile(self.path).read_column("id"),
                         [row["id"] for row in rows])

    def test_random_distributions_and_random_read_order(self):
        for seed in range(8):
            count = random.Random(seed * 97 + 3).randint(1, 160)
            rows = make_rows(count, seed)
            write_file(self.path, SCHEMA, rows)
            reader = ColumnFile(self.path)
            ref_rows, ref_row, ref_filter = naive_rows_match(rows, SCHEMA)
            self.assertEqual(reader.read_rows(), ref_rows())
            order = list(range(count))
            random.Random(seed + 100).shuffle(order)
            for index in order:
                self.assertEqual(reader.read_row(index), ref_row(index))
            for name, value in (("city", "北京"), ("amount", 7),
                                ("id", 5000), ("city", "月球"),
                                ("amount", 1000)):
                self.assertEqual(reader.filter_eq(name, value),
                                 ref_filter(name, value))

    def test_filter_type_mismatch_returns_empty(self):
        rows = make_rows(32, 3)
        write_file(self.path, SCHEMA, rows)
        reader = ColumnFile(self.path)
        self.assertEqual(reader.filter_eq("id", "5000"), [])
        self.assertEqual(reader.filter_eq("city", 1), [])
        with self.assertRaises(SchemaError):
            reader.filter_eq("nope", 1)


class SkipPageStatsTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        self._old_page_rows = store_module.PAGE_ROWS
        store_module.PAGE_ROWS = 10

    def tearDown(self):
        store_module.PAGE_ROWS = self._old_page_rows
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_miss_skips_every_page_and_decodes_none(self):
        rows = [{"id": index, "city": CITIES[index % 3], "amount": index}
                for index in range(50)]
        write_file(self.path, SCHEMA, rows)
        reader = ColumnFile(self.path)
        self.assertEqual(reader.filter_eq("city", "00_不存在"), [])
        stats = reader.stats()
        self.assertEqual(stats["skipped_pages"], 5)
        self.assertEqual(stats["decoded_pages"], 0)

    def test_hit_only_decodes_pages_in_range(self):
        rows = []
        for index in range(30):
            if index < 10:
                city = "北京"
            elif index < 20:
                city = "上海"
            else:
                city = "广州"
            rows.append({"id": index, "city": city, "amount": index})
        write_file(self.path, SCHEMA, rows)
        reader = ColumnFile(self.path)
        hits = reader.filter_eq("city", "北京")
        self.assertEqual([row["id"] for row in hits], list(range(10)))
        stats = reader.stats()
        # 北京只在第 0 页：标记列 1 页 + 另外两列各 1 页；其余两页跳过。
        self.assertEqual(stats["skipped_pages"], 2)
        self.assertEqual(stats["decoded_pages"], 3)

    def test_read_row_decodes_only_one_page_per_column(self):
        rows = make_rows(45, 5)
        write_file(self.path, SCHEMA, rows)
        reader = ColumnFile(self.path)
        self.assertEqual(reader.read_row(37), rows[37])
        self.assertEqual(reader.stats()["decoded_pages"], len(SCHEMA))

    def test_skipped_page_is_not_decoded_even_if_corrupt(self):
        rows = [{"id": index,
                 "city": ("北京" if index < 20 else "上海"),
                 "amount": index}
                for index in range(30)]
        write_file(self.path, SCHEMA, rows)
        reader = ColumnFile(self.path)
        column = reader.columns[1]
        offset, length, _ = column["pages"][2]
        with open(self.path, "rb") as handle:
            data = bytearray(handle.read())
        absolute = len(MAGIC) + column["offset"] + offset + 1
        data[absolute] ^= 0xFF
        with open(self.path, "wb") as handle:
            handle.write(data)
        reader = ColumnFile(self.path)
        # 第 2 页城市是“上海”，查“北京”：前两页正常解码、坏的第 2 页只看页头
        # 就被范围跳过，整页 payload 不能碰。
        hits = reader.filter_eq("city", "北京")
        self.assertEqual([row["id"] for row in hits], list(range(20)))
        stats = reader.stats()
        self.assertEqual(stats["skipped_pages"], 1)
        self.assertEqual(stats["decoded_pages"], 6)
        self.assertEqual(stats["bad_pages"], [])


class BadPageTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        self._old_page_rows = store_module.PAGE_ROWS
        store_module.PAGE_ROWS = 10
        self.rows = make_rows(35, 8)
        write_file(self.path, SCHEMA, self.rows)

    def tearDown(self):
        store_module.PAGE_ROWS = self._old_page_rows
        if os.path.exists(self.path):
            os.unlink(self.path)

    def corrupt(self, column_index, page_no):
        reader = ColumnFile(self.path)
        column = reader.columns[column_index]
        offset, length, _ = column["pages"][page_no]
        with open(self.path, "rb") as handle:
            data = bytearray(handle.read())
        page_start = len(MAGIC) + column["offset"] + offset
        head_len, used = decode_uvarint(data[page_start:page_start + 10], 0)
        payload_start = page_start + used + head_len
        payload_len = length - used - head_len - 4
        absolute = payload_start + min(2, max(payload_len - 1, 0))
        data[absolute] ^= 0xFF
        with open(self.path, "wb") as handle:
            handle.write(data)

    def test_sequential_read_skips_bad_page_and_records_it(self):
        self.corrupt(1, 2)
        reader = ColumnFile(self.path)
        rows = reader.read_rows()
        stats = reader.stats()
        self.assertEqual(stats["bad_pages"], [2])
        expected = [row for index, row in enumerate(self.rows)
                    if not 20 <= index < 30]
        self.assertEqual(rows, expected)

    def test_read_row_on_bad_page_raises_but_other_pages_survive(self):
        self.corrupt(1, 2)
        reader = ColumnFile(self.path)
        with self.assertRaises(BadPageError) as caught:
            reader.read_row(25)
        self.assertEqual(caught.exception.page, 2)
        self.assertEqual(reader.read_row(5), self.rows[5])
        self.assertEqual(reader.read_row(31), self.rows[31])

    def test_filter_skips_bad_page_number(self):
        self.corrupt(0, 1)
        reader = ColumnFile(self.path)
        # 第 1 页 id（过滤的标记列）坏了，命中行所在页解不开，跳过记 bad_pages。
        self.assertEqual(reader.filter_eq("id", 5015), [])
        self.assertEqual(reader.stats()["bad_pages"], [1])
        # 好页上的命中照常返回。
        good = reader.filter_eq("id", 5005)
        self.assertEqual([row["id"] for row in good], [5005])


class LegacyFormatTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def write_format_one(self, rows):
        columns = [("id", "int"), ("city", "str")]
        body = b""
        meta = []
        for name, kind in columns:
            blob = encode_raw(kind, [row[name] for row in rows])
            meta.append({"name": name, "kind": kind, "codec": "raw",
                         "offset": len(body), "length": len(blob)})
            body += blob
        footer = json.dumps(
            {"format": 1, "rows": len(rows), "columns": meta},
            ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with open(self.path, "wb") as handle:
            handle.write(MAGIC)
            handle.write(body)
            handle.write(footer)
            handle.write(struct.pack("<I", len(footer)))

    def test_upgrade_does_not_reject_old_files(self):
        rows = [{"id": index, "city": CITIES[index % 3]}
                for index in range(33)]
        self.write_format_one(rows)
        reader = ColumnFile(self.path)
        self.assertEqual(reader.format, 1)
        self.assertEqual(reader.read_rows(), rows)
        order = [7, 0, 32, 15, 1]
        self.assertEqual([reader.read_row(i) for i in order],
                         [rows[i] for i in order])
        self.assertEqual(reader.filter_eq("city", "北京"),
                         [row for row in rows if row["city"] == "北京"])


class StreamingWriteTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        self._old_page_rows = store_module.PAGE_ROWS
        store_module.PAGE_ROWS = 100

    def tearDown(self):
        store_module.PAGE_ROWS = self._old_page_rows
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_writer_does_not_buffer_the_whole_table(self):
        store = ColumnStore(self.path, SCHEMA)
        self.assertFalse(hasattr(store, "_rows"))
        for index in range(1000):
            store.append({"id": index, "city": CITIES[index % 3],
                          "amount": -index})
            for buffer in store._buffers:
                self.assertLessEqual(len(buffer.values), 100)
        store.close()
        rows = ColumnFile(self.path).read_rows()
        self.assertEqual(len(rows), 1000)
        self.assertEqual(rows[0],
                         {"id": 0, "city": CITIES[0], "amount": 0})
        self.assertEqual(rows[-1],
                         {"id": 999, "city": CITIES[999 % 3], "amount": -999})


class CompressionTest(unittest.TestCase):
    def test_target_columns_under_twenty_percent(self):
        handle, path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        try:
            count = 100_000
            rng = random.Random(11)

            def generate():
                for index in range(count):
                    yield {"id": 1_000_000 + index,
                           "city": CITIES[rng.randrange(len(CITIES))],
                           "amount": (index * 7) % 1000 - 500}

            write_file(path, SCHEMA, generate())
            reader = ColumnFile(path)
            for column in reader.columns:
                raw = count * 8 if column["kind"] == "int" else count * 7
                self.assertLess(column["length"], raw * 0.2,
                                "列 %s 没压进两成" % column["name"])
        finally:
            os.unlink(path)


class EmptyPagedTableTest(unittest.TestCase):
    def test_empty_table_has_no_pages(self):
        handle, path = tempfile.mkstemp(suffix=".col")
        os.close(handle)
        try:
            write_file(path, SCHEMA, [])
            reader = ColumnFile(path)
            self.assertEqual(reader.read_rows(), [])
            self.assertEqual(reader.read_column("id"), [])
            with self.assertRaises(IndexError):
                reader.read_row(0)
            self.assertEqual(reader.filter_eq("city", "北京"), [])
            self.assertEqual(reader.stats()["decoded_pages"], 0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
