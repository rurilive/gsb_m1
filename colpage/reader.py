"""读取端：整表顺序读、按行号随机读、按列等值过滤。

基线实现是朴素的，每个入口都先把用到的列整段解开再挑。
"""

import json
import os
import struct

from colpage.codec import decode_segment
from colpage.errors import FormatError
from colpage.schema import Schema
from colpage.store import MAGIC


class ColumnFile:
    """打开的列文件，只读。

    read_rows() 顺序读回整表，read_row(i) 按行号取一行，
    filter_eq(列, 值) 等值过滤，文件不对抛 FormatError。
    """

    def __init__(self, path):
        self.path = path
        self._size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if self._size < len(MAGIC) + 4:
                raise FormatError("文件太短，放不下框架: %s" % path)
            handle.seek(0)
            magic = handle.read(len(MAGIC))
            if magic != MAGIC:
                raise FormatError("魔数不对: %r" % (magic,))
            handle.seek(self._size - 4)
            footer_size = struct.unpack("<I", handle.read(4))[0]
            if footer_size > self._size - len(MAGIC) - 4:
                raise FormatError("footer 长度 %d 放不进文件" % footer_size)
            handle.seek(self._size - 4 - footer_size)
            raw_footer = handle.read(footer_size)
        try:
            footer = json.loads(raw_footer.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise FormatError("footer 解不开: %s" % exc)
        try:
            self.format = footer["format"]
            self.row_count = footer["rows"]
            self.columns = footer["columns"]
            self.schema = Schema([(column["name"], column["kind"])
                                  for column in self.columns])
        except (KeyError, TypeError) as exc:
            raise FormatError("footer 缺字段: %s" % exc)

    def _segment_bytes(self, index):
        column = self.columns[index]
        with open(self.path, "rb") as handle:
            handle.seek(len(MAGIC) + column["offset"])
            blob = handle.read(column["length"])
        if len(blob) != column["length"]:
            raise FormatError("列 %s 的段读不全" % column["name"])
        return blob

    def read_column(self, name):
        """整列读出来，值序与写入时一致。"""
        index = self.schema.index(name)
        column = self.columns[index]
        try:
            values = decode_segment(column["kind"], self._segment_bytes(index),
                                    column.get("codec", "raw"))
        except FormatError as exc:
            raise FormatError("列 %s: %s" % (name, exc))
        if len(values) != self.row_count:
            raise FormatError("列 %s 解出 %d 个值，表里有 %d 行"
                              % (name, len(values), self.row_count))
        return values

    def read_rows(self):
        """顺序读回整表，行序与写入时一致。"""
        columns = [self.read_column(name) for name in self.schema.names]
        return [{name: values[index] for name, values in zip(self.schema.names, columns)}
                for index in range(self.row_count)]

    def read_row(self, index):
        """按行号取一行，越界抛 IndexError。"""
        if index < 0 or index >= self.row_count:
            raise IndexError("行号 %r 越界，一共 %d 行" % (index, self.row_count))
        columns = [self.read_column(name) for name in self.schema.names]
        return {name: values[index] for name, values in zip(self.schema.names, columns)}

    def filter_eq(self, column, value):
        """等值过滤：按行序返回命中的行。"""
        self.schema.index(column)
        columns = [self.read_column(name) for name in self.schema.names]
        marker = self.schema.index(column)
        hits = [index for index, item in enumerate(columns[marker]) if item == value]
        return [{name: values[index]
                 for name, values in zip(self.schema.names, columns)}
                for index in hits]

    def stats(self):
        """文件与读取状态的摘要。"""
        return {"rows": self.row_count, "columns": len(self.schema),
                "file_bytes": self._size}

    def __repr__(self):
        return "ColumnFile(%r, rows=%d)" % (self.path, self.row_count)
