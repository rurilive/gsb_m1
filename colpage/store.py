"""写入端：行按列拆开，每 N 行一页编码后顺序写进本地文件。

文件结构（小端）：偏移 0 是 8 字节魔数，随后各列数据段一列一段首尾相接，
再往后是 footer 的 JSON，末尾 4 字节 uint32 是 footer 的字节数。

format 2 的列段是分页的（codec ``paged``）：页首尾相接，页头记编码与
min/max，页尾带 CRC32，具体格式见 ``colpage.pager``。写端为每列维护
一页大小的内存缓冲，页满就编码落到同目录的临时文件，整表从不进内存。
"""

import json
import os
import struct
import tempfile

from colpage.errors import SchemaError
from colpage.pager import encode_page
from colpage.schema import Schema

MAGIC = b"colpage1"
FORMAT = 2
PAGED = "paged"
PAGE_ROWS = 65536


def write_file(path, schema, rows):
    """一口气写好一个列文件，返回写入的行数。"""
    store = ColumnStore(path, schema)
    with store:
        for row in rows:
            store.append(row)
    return store.row_count


class _ColumnBuffer:
    """单列缓冲：攒满一页就编码进临时文件，只保留一页在内存。"""

    def __init__(self, kind, page_rows, spool_dir):
        self.kind = kind
        self.page_rows = page_rows
        self.spool_dir = spool_dir
        self.values = []
        self.state = {}
        self.spool = None
        self.pages = []

    def add(self, value):
        self.values.append(value)
        if len(self.values) >= self.page_rows:
            self.flush()

    def flush(self):
        if not self.values:
            return
        blob, self.state = encode_page(self.kind, self.values, self.state)
        if self.spool is None:
            self.spool = tempfile.TemporaryFile(dir=self.spool_dir)
        offset = self.spool.tell()
        self.spool.write(blob)
        self.pages.append((offset, len(blob), len(self.values)))
        self.values = []

    def finish(self):
        """落最后一页，返回 (段字节, 页目录)；空列返回 (b"", [])。"""
        self.flush()
        pages = list(self.pages)
        if self.spool is None:
            return b"", pages
        self.spool.seek(0)
        return self.spool.read(), pages

    def close(self):
        if self.spool is not None:
            self.spool.close()
            self.spool = None


class ColumnStore:
    """列文件写入器。

    append() 收一行，close() 落盘，也可以当上下文管理器用。
    行按列拆进每列一页大小的缓冲，页满即编码落临时文件，内存只占一页。
    """

    def __init__(self, path, schema):
        if not isinstance(schema, Schema):
            raise SchemaError("schema 得是 Schema，收到 %r" % (schema,))
        self.path = path
        self.schema = schema
        self.row_count = 0
        self.closed = False
        spool_dir = os.path.dirname(os.path.abspath(path)) or "."
        self._buffers = [_ColumnBuffer(kind, PAGE_ROWS, spool_dir)
                         for _, kind in schema.columns]

    def append(self, row):
        """收一行，字段不合格抛 SchemaError。"""
        if self.closed:
            raise ValueError("写入器已经关过了")
        self.schema.validate_row(row)
        for index, (name, _) in enumerate(self.schema.columns):
            self._buffers[index].add(row[name])
        self.row_count += 1

    def close(self):
        """把各列段拼好写出并收尾，重复调用没事。"""
        if self.closed:
            return
        body = bytearray()
        columns = []
        for (name, kind), buffer in zip(self.schema.columns, self._buffers):
            blob, pages = buffer.finish()
            directory = [[offset, length, nrows]
                         for offset, length, nrows in pages]
            columns.append({"name": name, "kind": kind, "codec": PAGED,
                            "offset": len(body), "length": len(blob),
                            "pages": directory})
            body += blob
        footer = {"format": FORMAT, "rows": self.row_count, "columns": columns}
        raw_footer = json.dumps(footer, ensure_ascii=False,
                                separators=(",", ":")).encode("utf-8")
        with open(self.path, "wb") as out:
            out.write(MAGIC)
            out.write(bytes(body))
            out.write(raw_footer)
            out.write(struct.pack("<I", len(raw_footer)))
        for buffer in self._buffers:
            buffer.close()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.close()
        else:
            for buffer in self._buffers:
                buffer.close()
        return False

    def __repr__(self):
        return "ColumnStore(%r, rows=%d)" % (self.path, self.row_count)
