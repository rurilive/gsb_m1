"""追加型的本地日志文件。

一行一条记录，只管写和扫，不管记录里是什么。尾部没写完的半行
（进程被杀、磁盘写了一半）扫描时跳过，中间出现解不开的行就是
文件真坏了，抛 CorruptLogError，不吞。
"""

import os
import threading

from auditchain.codec import RecordError, decode_line, encode_line


class CorruptLogError(Exception):
    """日志文件里出现了解不开的行，位置在 offset 上。"""

    def __init__(self, message, offset=None):
        super().__init__(message)
        self.offset = offset


class RecordStore:
    """一个文件一个 store。追加写，扫描按文件顺序返回偏移和记录。"""

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def append(self, record):
        """追加一条完整记录，返回写完之后文件的总字节数。"""
        blob = encode_line(record)
        with self._lock:
            with open(self.path, "ab") as handle:
                handle.write(blob)
                handle.flush()
            return os.path.getsize(self.path)

    def scan(self):
        """从头扫一遍，返回 (entries, valid_end)。

        entries 是 (偏移, 记录) 的列表，按文件顺序排。
        valid_end 是最后一条完整记录的结束偏移，尾巴上没写完的半行
        不计入，也不会因此报错。文件不存在当空文件处理。
        """
        try:
            with open(self.path, "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            return [], 0

        entries = []
        valid_end = 0
        offset = 0
        while True:
            newline = data.find(b"\n", offset)
            if newline < 0:
                break
            line = data[offset:newline]
            try:
                record = decode_line(line)
            except RecordError as exc:
                raise CorruptLogError(
                    "bad record at offset %d: %s" % (offset, exc), offset=offset
                ) from exc
            entries.append((offset, record))
            offset = newline + 1
            valid_end = offset
        return entries, valid_end

    def scan_prefix(self, start=0):
        """从 start 偏移尽量往后扫，返回 (entries, corrupt_offset)。

        和 scan 一样是 (偏移, 记录) 的列表，但遇到解不开的行不抛错，
        把那一行的偏移放在 corrupt_offset 里返回，后面的内容不再看；
        一路顺利 corrupt_offset 就是 None。尾部没写完的半行不算坏。
        """
        try:
            with open(self.path, "rb") as handle:
                handle.seek(start)
                data = handle.read()
        except FileNotFoundError:
            return [], None

        entries = []
        offset = 0
        while True:
            newline = data.find(b"\n", offset)
            if newline < 0:
                return entries, None
            line = data[offset:newline]
            try:
                record = decode_line(line)
            except RecordError:
                return entries, start + offset
            entries.append((start + offset, record))
            offset = newline + 1

    def read_at(self, offset):
        """读出从指定偏移开始的那条记录，返回 (记录, 下一条的偏移)。

        偏移越界、行没写完、行解不开，都返回 None。
        """
        try:
            with open(self.path, "rb") as handle:
                handle.seek(offset)
                line = handle.readline()
        except (OSError, ValueError):
            return None
        if not line.endswith(b"\n"):
            return None
        try:
            record = decode_line(line)
        except RecordError:
            return None
        return record, offset + len(line)

    def rewrite(self, records):
        """整份重写：把 records 按顺序写回，原来的内容全部换掉。"""
        blob = b"".join(encode_line(record) for record in records)
        with self._lock:
            with open(self.path, "wb") as handle:
                handle.write(blob)
                handle.flush()
        return len(blob)

    def truncate(self, offset):
        """把文件截到指定偏移，用来丢掉没写完的尾巴。"""
        with self._lock:
            if not os.path.exists(self.path):
                return
            with open(self.path, "r+b") as handle:
                handle.truncate(offset)

    def size(self):
        """文件当前字节数，文件不存在按 0 算。"""
        try:
            return os.path.getsize(self.path)
        except FileNotFoundError:
            return 0
