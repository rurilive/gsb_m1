"""按条裸存后端：原有 16 字节定长记录格式，一字节不动的语义。

老文件继续用本后端读写，保持“只增不改”的追加规矩；块压缩只对新
文件生效，老文件不迁移。
"""

import os

from .errors import OutOfOrderError
from .layout import (
    HEADER,
    RECORD,
    pack_record,
    record_count,
    unpack_record,
    validate_header,
)

#: 顺序读时每批读多少条记录。
_BATCH = 512


class RawStore:
    """本地文件里的时间点序列（裸存格式）。"""

    def __init__(self, path):
        self._path = str(path)
        self._appends = 0
        self._reads = 0
        self._fh = None
        try:
            if os.path.exists(self._path) and os.path.getsize(self._path) > 0:
                self._fh = open(self._path, "r+b")
                self._fh.seek(0)
                validate_header(self._fh.read(len(HEADER)))
            else:
                self._fh = open(self._path, "w+b")
                self._fh.write(HEADER)
                self._fh.flush()
            self._fh.seek(0, os.SEEK_END)
            self._count = record_count(self._fh.tell())
            self._last_ts = self._peek_last_ts()
        except Exception:
            self.close()
            raise

    # ---- 写入 ----

    def append(self, ts, value):
        """追加一条。时间戳小于上一条时抛 OutOfOrderError。"""
        self._check_pair(ts, value)
        if self._last_ts is not None and ts < self._last_ts:
            raise OutOfOrderError(
                "时间戳 %r 小于上一条 %r，拒绝写入" % (ts, self._last_ts)
            )
        self._write_pair(ts, value)

    def append_many(self, pairs):
        """整批追加，任何一条不合法整批拒绝，文件不动。"""
        items = [(ts, value) for ts, value in pairs]
        prev = self._last_ts
        for ts, value in items:
            self._check_pair(ts, value)
            if prev is not None and ts < prev:
                raise OutOfOrderError(
                    "批内时间戳 %r 小于前一条 %r，整批拒绝" % (ts, prev)
                )
            prev = ts
        for ts, value in items:
            self._write_pair(ts, value)

    @staticmethod
    def _check_pair(ts, value):
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise TypeError("时间戳必须是 int，收到 %r" % type(ts).__name__)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("值必须是 int 或 float，收到 %r" % type(value).__name__)

    def _write_pair(self, ts, value):
        self._fh.seek(0, os.SEEK_END)
        self._fh.write(pack_record(ts, value))
        self._count += 1
        self._last_ts = ts
        self._appends += 1

    # ---- 读取 ----

    def read_at(self, index):
        """按下标读一条，支持负数下标，越界抛 IndexError。"""
        i = index + self._count if index < 0 else index
        if i < 0 or i >= self._count:
            raise IndexError("下标 %r 越界（共 %d 条）" % (index, self._count))
        self._fh.seek(len(HEADER) + i * RECORD.size)
        ts, value = unpack_record(self._fh.read(RECORD.size))
        self._reads += 1
        return (ts, value)

    def find(self, ts):
        """第一个时间戳不小于 ts 的下标；全都小于 ts 时返回 -1。"""
        start = 0
        self._fh.seek(len(HEADER))
        while start < self._count:
            n = min(_BATCH, self._count - start)
            buf = self._fh.read(n * RECORD.size)
            if not buf:
                break
            for k, (cur, _) in enumerate(RECORD.iter_unpack(buf)):
                if cur >= ts:
                    self._reads += 1
                    return start + k
            start += n
        self._reads += 1
        return -1

    def __iter__(self):
        """按写入顺序流式迭代，一批一批读。"""
        self._fh.seek(len(HEADER))
        remaining = self._count
        while remaining > 0:
            n = min(_BATCH, remaining)
            buf = self._fh.read(n * RECORD.size)
            if not buf:
                break
            for pair in RECORD.iter_unpack(buf):
                self._reads += 1
                yield pair
            remaining -= n

    def read_all(self):
        """读出全部记录，返回 (时间戳, 值) 列表。"""
        return list(self)

    def __len__(self):
        return self._count

    # ---- 元信息 ----

    @property
    def path(self):
        return self._path

    @property
    def last_ts(self):
        """最后一条的时间戳，空库返回 None。"""
        return self._last_ts

    def stats(self):
        """计数快照，返回新字典。"""
        return {
            "records": self._count,
            "bytes_on_disk": len(HEADER) + self._count * RECORD.size,
            "appends": self._appends,
            "reads": self._reads,
            "decoded_blocks": 0,
            "bad_blocks": 0,
        }

    def close(self):
        """刷盘并关闭，可重复调用。"""
        if self._fh is not None and not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def _peek_last_ts(self):
        if self._count == 0:
            return None
        self._fh.seek(len(HEADER) + (self._count - 1) * RECORD.size)
        ts, _ = unpack_record(self._fh.read(RECORD.size))
        return ts
