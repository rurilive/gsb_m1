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

    def truncate(self, offset):
        """把文件截到指定偏移，用来丢掉没写完的尾巴。"""
        with self._lock:
            if not os.path.exists(self.path):
                return
            with open(self.path, "r+b") as handle:
                handle.truncate(offset)

    def rewrite_all(self, records):
        """整文件原子重写，给老日志就地补链用。

        先写临时文件再改名，中途崩了原文件还在。记录按给的顺序落盘，
        返回新文件的总字节数。
        """
        tmp_path = "%s.tmp.%d" % (self.path, os.getpid())
        with self._lock:
            try:
                with open(tmp_path, "wb") as handle:
                    for record in records:
                        handle.write(encode_line(record))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, self.path)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            return os.path.getsize(self.path)

    def size(self):
        """文件当前字节数，文件不存在按 0 算。"""
        try:
            return os.path.getsize(self.path)
        except FileNotFoundError:
            return 0


class CheckpointStore:
    """检查点侧车文件，同样一行一条 JSON，只追加。

    检查点固化到第 seq 条为止的链头摘要 digest，巡检可以从这里起步，
    不用每条都从头算。每个检查点自带签名，手改或伪造的检查点会被
    verify 忽略；尾部没写完的半行直接跳过。
    """

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def append(self, entry):
        """固化一个检查点，返回侧车文件新的总字节数。"""
        blob = encode_line(entry)
        with self._lock:
            with open(self.path, "ab") as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            return os.path.getsize(self.path)

    def read_all(self):
        """读回全部写完整的检查点，按文件顺序。半行或坏行一律跳过。"""
        try:
            with open(self.path, "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            return []

        entries = []
        offset = 0
        while True:
            newline = data.find(b"\n", offset)
            if newline < 0:
                break
            try:
                record = decode_line(data[offset:newline])
            except RecordError:
                record = None
            if isinstance(record, dict):
                entries.append(record)
            offset = newline + 1
        return entries

    def size(self):
        """侧车文件当前字节数，不存在按 0 算。"""
        try:
            return os.path.getsize(self.path)
        except FileNotFoundError:
            return 0
