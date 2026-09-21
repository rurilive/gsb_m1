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

    def replace(self, records):
        """整文件原子替换，老日志就地补链时用。

        先写临时文件再 os.replace，进程中途被杀也只会留下旧文件，
        不会看到补了一半的链。返回新文件字节数。
        """
        blob = b"".join(encode_line(record) for record in records)
        with self._lock:
            tmp_path = "%s.tmp%d" % (self.path, os.getpid())
            try:
                with open(tmp_path, "wb") as handle:
                    handle.write(blob)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, self.path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
            return len(blob)

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

    def size(self):
        """文件当前字节数，文件不存在按 0 算。"""
        try:
            return os.path.getsize(self.path)
        except FileNotFoundError:
            return 0
