"""写入端：把行记录按列拆开，顺序写进本地文件。

文件结构（小端）：偏移 0 是 8 字节魔数，随后各列数据段一列一段首尾相接，
再往后是 footer 的 JSON（记行数、每段偏移与长度、段编码），
末尾 4 字节 uint32 是 footer 的字节数。基线实现把行先攒在内存里，
close() 时逐列整段写出。
"""

import json
import struct

from colpage.codec import RAW, encode_segment
from colpage.errors import SchemaError
from colpage.schema import Schema

MAGIC = b"colpage1"
FORMAT = 1


def write_file(path, schema, rows):
    """一口气写好一个列文件，返回写入的行数。"""
    store = ColumnStore(path, schema)
    with store:
        for row in rows:
            store.append(row)
    return store.row_count


class ColumnStore:
    """列文件写入器。

    append() 收一行，close() 落盘，也可以当上下文管理器用。
    """

    def __init__(self, path, schema):
        if not isinstance(schema, Schema):
            raise SchemaError("schema 得是 Schema，收到 %r" % (schema,))
        self.path = path
        self.schema = schema
        self.row_count = 0
        self.closed = False
        self._rows = []

    def append(self, row):
        """收一行，字段不合格抛 SchemaError。"""
        if self.closed:
            raise ValueError("写入器已经关过了")
        self.schema.validate_row(row)
        self._rows.append(dict(row))
        self.row_count += 1

    def close(self):
        """把攒下的行整列写出并收尾，重复调用没事。"""
        if self.closed:
            return
        body = bytearray()
        columns = []
        for name, kind in self.schema.columns:
            blob = encode_segment(kind, [row[name] for row in self._rows], RAW)
            columns.append({"name": name, "kind": kind, "codec": RAW,
                            "offset": len(body), "length": len(blob)})
            body += blob
        footer = {"format": FORMAT, "rows": len(self._rows), "columns": columns}
        raw_footer = json.dumps(footer, ensure_ascii=False,
                                separators=(",", ":")).encode("utf-8")
        with open(self.path, "wb") as out:
            out.write(MAGIC)
            out.write(bytes(body))
            out.write(raw_footer)
            out.write(struct.pack("<I", len(raw_footer)))
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.close()
        return False

    def __repr__(self):
        return "ColumnStore(%r, rows=%d)" % (self.path, self.row_count)
