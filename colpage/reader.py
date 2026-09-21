"""读取端：整表顺序读、按行号随机读、按列等值过滤。

format 2 的列段是分页编码段（codec ``paged``）：

- read_row(i) 只按 footer 里的页目录定位并解目标行所在的那一页；
- filter_eq 先扫页头 min/max，值不在范围内的页整页跳过（只读几字节
  页头、不校验 payload、不计 decoded_pages），落在范围内的页才解码；
- 顺序读碰到页头/页尾校验不过的坏页：跳过该页、页号记进 stats 的
  bad_pages，其余页照常读；read_row 正好落到坏页则抛 BadPageError。

format 1 的旧文件（codec raw、整段不压缩）照旧能读，入口不拒收。
"""

import json
import os
import struct

from colpage.codec import RAW, decode_raw, decode_uvarint
from colpage.errors import BadPageError, FormatError
from colpage.pager import decode_page, parse_page_header
from colpage.schema import Schema
from colpage.store import MAGIC, PAGED


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
        if self.format not in (1, 2):
            raise FormatError("不认识的文件格式版本: %r" % (self.format,))
        if not isinstance(self.row_count, int) or self.row_count < 0:
            raise FormatError("行数不合法: %r" % (self.row_count,))
        if not isinstance(self.columns, list):
            raise FormatError("footer 里 columns 不是列表")
        for column in self.columns:
            codec = column.get("codec", RAW)
            if codec not in (RAW, PAGED):
                raise FormatError("列 %s 用了不认识的编码: %r"
                                  % (column.get("name"), codec))
            if codec == PAGED:
                pages = column.get("pages")
                if not isinstance(pages, list):
                    raise FormatError("列 %s 缺页目录" % column.get("name"))
                for entry in pages:
                    if (not isinstance(entry, list) or len(entry) != 3
                            or not all(isinstance(item, int) for item in entry)):
                        raise FormatError("列 %s 的页目录项不合法"
                                          % column.get("name"))
        self._decoded_pages = 0
        self._skipped_pages = 0
        self._bad_pages = []

    # ------------------------------------------------------------------
    # 底层读取
    # ------------------------------------------------------------------

    def _open(self):
        return open(self.path, "rb")

    def _segment_from(self, handle, column, offset, length):
        handle.seek(len(MAGIC) + column["offset"] + offset)
        blob = handle.read(length)
        if len(blob) != length:
            raise FormatError("列 %s 的段读不全" % column["name"])
        return blob

    def _decode_all_raw(self, column):
        with self._open() as handle:
            blob = self._segment_from(handle, column, 0, column["length"])
        return decode_raw(column["kind"], blob)

    def _page_blob(self, handle, column, page_no):
        offset, length, _ = column["pages"][page_no]
        return self._segment_from(handle, column, offset, length)

    def _decode_page(self, handle, column, page_no):
        """读并解列段里的一页；坏页抛带页号的 BadPageError。"""
        blob = self._page_blob(handle, column, page_no)
        try:
            values, _ = decode_page(column["kind"], blob, 0)
        except BadPageError as exc:
            raise BadPageError(str(exc), page=page_no)
        self._decoded_pages += 1
        return values

    def _decode_paged_column(self, column):
        """顺序解完整列；坏页跳过并记页号，不废掉整列。

        返回 (values, 本次跳过的坏页行数)。
        """
        values = []
        bad_rows = 0
        with self._open() as handle:
            for page_no in range(len(column["pages"])):
                try:
                    values.extend(self._decode_page(handle, column, page_no))
                except BadPageError as exc:
                    self._record_bad(exc.page)
                    bad_rows += column["pages"][page_no][2]
        return values, bad_rows

    def _record_bad(self, page_no):
        if page_no is not None and page_no not in self._bad_pages:
            self._bad_pages.append(page_no)

    @staticmethod
    def _page_for_row(column, row_index):
        """行号落在哪一页：优先页目录的行数累加，兜底按等大页推算。"""
        start = 0
        for page_no, (_, _, nrows) in enumerate(column["pages"]):
            end = start + nrows
            if row_index < end:
                return page_no, start
            start = end
        raise FormatError("页目录的行数对不上总行数")

    # ------------------------------------------------------------------
    # 对外读取
    # ------------------------------------------------------------------

    def read_column(self, name):
        """整列读出来，值序与写入时一致；坏页会被跳过。"""
        index = self.schema.index(name)
        column = self.columns[index]
        try:
            if column.get("codec", RAW) == RAW:
                values = self._decode_all_raw(column)
                self._decoded_pages += 1
                bad_rows = 0
            else:
                values, bad_rows = self._decode_paged_column(column)
        except FormatError as exc:
            raise FormatError("列 %s: %s" % (name, exc))
        if len(values) != self.row_count - bad_rows:
            raise FormatError("列 %s 解出 %d 个值，表里有 %d 行"
                              % (name, len(values), self.row_count))
        return values

    def read_rows(self):
        """顺序读回整表，行序与写入时一致；坏页的行整段跳过。"""
        page_count = (len(self.columns[0]["pages"])
                      if self.format == 2 and self.columns else 0)
        if page_count == 0:
            columns = [self.read_column(name) for name in self.schema.names]
            return [{name: values[index]
                     for name, values in zip(self.schema.names, columns)}
                    for index in range(self.row_count)]
        rows = []
        with self._open() as handle:
            for page_no in range(page_count):
                page_columns = []
                bad = False
                for column in self.columns:
                    try:
                        page_columns.append(
                            self._decode_page(handle, column, page_no))
                    except BadPageError as exc:
                        self._record_bad(exc.page)
                        bad = True
                        break
                if bad:
                    continue
                nrows = len(page_columns[0])
                for within in range(nrows):
                    rows.append({name: values[within]
                                 for name, values
                                 in zip(self.schema.names, page_columns)})
        return rows

    def read_row(self, index):
        """按行号取一行，越界抛 IndexError；落到坏页抛 BadPageError。"""
        if index < 0 or index >= self.row_count:
            raise IndexError("行号 %r 越界，一共 %d 行" % (index, self.row_count))
        if self.format == 1 or any(column.get("codec", RAW) == RAW
                                   for column in self.columns):
            columns = [self.read_column(name) for name in self.schema.names]
            return {name: values[index]
                    for name, values in zip(self.schema.names, columns)}
        row = {}
        with self._open() as handle:
            for name, column in zip(self.schema.names, self.columns):
                page_no, start = self._page_for_row(column, index)
                values = self._decode_page(handle, column, page_no)
                row[name] = values[index - start]
        return row

    def filter_eq(self, column, value):
        """等值过滤：按行序返回命中的行；先页头 min/max 跳页。"""
        marker = self.schema.index(column)
        marker_column = self.columns[marker]
        kind = self.schema.columns[marker][1]
        if (kind == "int" and (not isinstance(value, int)
                               or isinstance(value, bool))) or (
                kind == "str" and not isinstance(value, str)):
            return []
        if marker_column.get("codec", RAW) == RAW:
            return self._filter_raw(column, value, marker)

        pages = marker_column["pages"]
        rows = []
        with self._open() as handle:
            for page_no in range(len(pages)):
                if not self._page_can_match(handle, marker_column,
                                            page_no, value):
                    self._skipped_pages += 1
                    continue
                try:
                    markers = self._decode_page(handle, marker_column, page_no)
                except BadPageError as exc:
                    self._record_bad(exc.page)
                    continue
                within_hits = [pos for pos, item in enumerate(markers)
                               if item == value]
                if not within_hits:
                    continue
                decoded = {}
                bad = False
                for col_no, col in enumerate(self.columns):
                    if col_no == marker:
                        decoded[col_no] = markers
                        continue
                    try:
                        decoded[col_no] = self._decode_page(handle, col,
                                                             page_no)
                    except BadPageError as exc:
                        self._record_bad(exc.page)
                        bad = True
                        break
                if bad:
                    continue
                start = sum(entry[2] for entry in pages[:page_no])
                for pos in within_hits:
                    rows.append({name: decoded[col_no][pos]
                                 for col_no, name
                                 in enumerate(self.schema.names)})
        return rows

    def _filter_raw(self, column, value, marker):
        columns = [self.read_column(name) for name in self.schema.names]
        hits = [index for index, item in enumerate(columns[marker])
                if item == value]
        return [{name: values[index]
                 for name, values in zip(self.schema.names, columns)}
                for index in hits]

    def _page_can_match(self, handle, column, page_no, value):
        """只读页头取 min/max；值不在范围里的页整页跳过，不算解码。"""
        offset, length, _ = column["pages"][page_no]
        handle.seek(len(MAGIC) + column["offset"] + offset)
        prefix = handle.read(10)
        try:
            head_len, used = decode_uvarint(prefix, 0)
        except FormatError:
            raise BadPageError("页头长度读不出来", page=page_no)
        rest = prefix[used:] + handle.read(head_len)
        blob = prefix[:used] + rest[:head_len]
        if len(rest) < head_len:
            raise BadPageError("页头读不全", page=page_no)
        header, _ = parse_page_header(column["kind"], blob, 0, verify=False)
        return header["min"] <= value <= header["max"]

    def stats(self):
        """文件与读取状态的摘要。

        decoded_pages: 实际解过 payload 的页次（旧 raw 段每次整段算 1）；
        skipped_pages: filter_eq 靠页头 min/max 整页跳过的页次；
        bad_pages: 读到校验不过、被跳过的页号列表（页号跨列一致）。
        """
        return {"rows": self.row_count, "columns": len(self.schema),
                "file_bytes": self._size,
                "decoded_pages": self._decoded_pages,
                "skipped_pages": self._skipped_pages,
                "bad_pages": list(self._bad_pages)}

    def __repr__(self):
        return "ColumnFile(%r, rows=%d)" % (self.path, self.row_count)
