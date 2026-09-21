"""压缩块后端：固定条数一块，块头走二分，读取只解所在块。

打开文件时顺序扫一遍块头建内存目录（坏块记序号并跳过，截断尾直接
丢弃），find 靠目录里的首末时间戳二分块头，read_at 只解码定位到的
那一块。满块立即落盘；最后一个没满的好块在重开时读回内存继续攒，
写满或关闭时再落盘，因此追加仍是只增不减、重复允许。
"""

import bisect
import os
import zlib

from .blocks import (
    BLOCK_HEADER,
    BLOCK_MAGIC,
    FILE_HEADER,
    decode_payload,
    pack_block,
    parse_header,
)
from .errors import OutOfOrderError, TsFormatError

#: 默认每块固定条数。
DEFAULT_BLOCK_SIZE = 10000

#: 校验块体时每次读多少，保证不把大块整个拖进内存。
_CRC_CHUNK = 1 << 16


class _Entry:
    """目录里的一个块（坏块也占位，保证序号稳定）。"""

    __slots__ = ("offset", "count", "base_ts", "last_ts", "payload_len", "bad")

    def __init__(self, offset, count, base_ts, last_ts, payload_len, bad):
        self.offset = offset
        self.count = count
        self.base_ts = base_ts
        self.last_ts = last_ts
        self.payload_len = payload_len
        self.bad = bad


class BlockStore:
    """本地文件里的时间点序列（块压缩格式）。"""

    def __init__(self, path, block_size=DEFAULT_BLOCK_SIZE):
        self._path = str(path)
        if isinstance(block_size, bool) or not isinstance(block_size, int):
            raise TypeError("block_size 必须是 int")
        if block_size <= 0:
            raise ValueError("block_size 必须为正整数")
        self._block_size = block_size
        self._appends = 0
        self._reads = 0
        self._decoded_blocks = 0
        self._bad_blocks = 0
        self._entries = []
        # 与 _entries 对齐：该块之前好块的累计条数。
        self._before = []
        self._good_idx = []
        self._good_last = []
        self._count = 0
        self._pending = []
        self._fh = None
        try:
            if os.path.exists(self._path) and os.path.getsize(self._path) > 0:
                self._fh = open(self._path, "r+b")
                self._fh.seek(0)
                head = self._fh.read(FILE_HEADER.size)
                if len(head) < FILE_HEADER.size:
                    raise TsFormatError("块文件头被截断")
                magic, stored_size = FILE_HEADER.unpack(head)
                if magic != BLOCK_MAGIC:
                    raise TsFormatError("文件头魔数不匹配，不是 tstore 块文件")
                if stored_size <= 0:
                    raise TsFormatError("块文件头里的块大小非法")
                self._block_size = stored_size
                self._scan_blocks()
                self._recover_tail()
            else:
                self._fh = open(self._path, "w+b")
                self._fh.write(FILE_HEADER.pack(BLOCK_MAGIC, self._block_size))
                self._fh.flush()
            self._fh.seek(0, os.SEEK_END)
        except Exception:
            self.close()
            raise

    # ---- 打开时建目录 ----

    def _scan_blocks(self):
        size = os.fstat(self._fh.fileno()).st_size
        pos = FILE_HEADER.size
        end = size
        while pos < size:
            if size - pos < BLOCK_HEADER.size:
                # 块头截断，只能是尾巴；丢掉并记一个坏块。
                end = pos
                self._bad_blocks += 1
                break
            self._fh.seek(pos)
            head = self._fh.read(BLOCK_HEADER.size)
            try:
                info = parse_header(head)
            except TsFormatError:
                # 标记错位后无法重新定界，按坏尾处理。
                end = pos
                self._bad_blocks += 1
                break
            block_end = pos + BLOCK_HEADER.size + info["payload_len"]
            if block_end > size:
                # 块体截断的尾巴。
                end = pos
                self._bad_blocks += 1
                break
            bad = (
                info["count"] == 0
                or info["count"] > self._block_size
                or info["last_ts"] < info["base_ts"]
                or not self._crc_matches(
                    pos + BLOCK_HEADER.size,
                    info["payload_len"],
                    info["crc"],
                )
            )
            self._register(
                _Entry(
                    pos,
                    info["count"],
                    info["base_ts"],
                    info["last_ts"],
                    info["payload_len"],
                    bad,
                )
            )
            if bad:
                self._bad_blocks += 1
            pos = block_end
        if end < size:
            self._fh.truncate(end)
            self._fh.flush()

    def _crc_matches(self, payload_off, length, expected):
        self._fh.seek(payload_off)
        crc = 0
        remaining = length
        while remaining:
            chunk = self._fh.read(min(_CRC_CHUNK, remaining))
            if not chunk:
                return False
            crc = zlib.crc32(chunk, crc)
            remaining -= len(chunk)
        return (crc & 0xFFFFFFFF) == expected

    def _register(self, entry, before=None, count=True):
        self._before.append(self._count if before is None else before)
        self._entries.append(entry)
        if not entry.bad:
            self._good_idx.append(len(self._entries) - 1)
            self._good_last.append(entry.last_ts)
            if count:
                self._count += entry.count

    def _mark_bad(self, idx):
        """解码时才发现的坏块：从目录里摘掉，序号仍保留占位。"""
        entry = self._entries[idx]
        if entry.bad:
            return
        entry.bad = True
        self._bad_blocks += 1
        self._count -= entry.count
        for j in range(idx + 1, len(self._before)):
            self._before[j] -= entry.count
        gj = bisect.bisect_left(self._good_idx, idx)
        if gj < len(self._good_idx) and self._good_idx[gj] == idx:
            self._good_idx.pop(gj)
            self._good_last.pop(gj)

    def _recover_tail(self):
        """末尾没满的好块读回内存，块从文件上摘掉继续攒。"""
        if not self._entries:
            return
        idx = len(self._entries) - 1
        entry = self._entries[idx]
        if entry.bad or entry.count >= self._block_size:
            return
        before = self._decoded_blocks
        timestamps, values = self._decode(idx, entry, with_values=True)
        if timestamps is None:
            self._decoded_blocks = before
            return
        self._pending = list(zip(timestamps, values))
        self._fh.truncate(entry.offset)
        self._fh.flush()
        self._entries.pop()
        self._before.pop()
        gj = bisect.bisect_left(self._good_idx, idx)
        self._good_idx.pop(gj)
        self._good_last.pop(gj)

    # ---- 写入 ----

    def append(self, ts, value):
        """追加一条。时间戳小于已知最后一条时抛 OutOfOrderError。"""
        self._check_pair(ts, value)
        anchor = self._anchor_ts()
        if anchor is not None and ts < anchor:
            raise OutOfOrderError(
                "时间戳 %r 小于上一条 %r，拒绝写入" % (ts, anchor)
            )
        self._pending.append((ts, value))
        self._count += 1
        self._appends += 1
        if len(self._pending) >= self._block_size:
            self._flush()

    def append_many(self, pairs):
        """整批追加，任何一条不合法整批拒绝，文件不动。"""
        items = [(ts, value) for ts, value in pairs]
        prev = self._anchor_ts()
        for ts, value in items:
            self._check_pair(ts, value)
            if prev is not None and ts < prev:
                raise OutOfOrderError(
                    "批内时间戳 %r 小于前一条 %r，整批拒绝" % (ts, prev)
                )
            prev = ts
        for ts, value in items:
            self._pending.append((ts, value))
            self._count += 1
            self._appends += 1
            if len(self._pending) >= self._block_size:
                self._flush()

    @staticmethod
    def _check_pair(ts, value):
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise TypeError("时间戳必须是 int，收到 %r" % type(ts).__name__)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("值必须是 int 或 float，收到 %r" % type(value).__name__)

    def _anchor_ts(self):
        if self._pending:
            return self._pending[-1][0]
        if self._good_last:
            return self._good_last[-1]
        return None

    def _flush(self):
        pairs = self._pending
        if not pairs:
            return
        self._fh.seek(0, os.SEEK_END)
        offset = self._fh.tell()
        buf = pack_block(pairs)
        self._fh.write(buf)
        before = self._count - len(pairs)
        self._register(
            _Entry(
                offset,
                len(pairs),
                pairs[0][0],
                pairs[-1][0],
                len(buf) - BLOCK_HEADER.size,
                False,
            ),
            before=before,
            count=False,
        )
        self._pending = []

    # ---- 读取 ----

    def read_at(self, index):
        """按下标读一条，只解码它所在的块；支持负数下标。"""
        i = index + self._count if index < 0 else index
        if i < 0 or i >= self._count:
            raise IndexError("下标 %r 越界（共 %d 条）" % (index, self._count))
        flushed = self._count - len(self._pending)
        if i >= flushed:
            self._reads += 1
            return self._pending[i - flushed]
        idx = bisect.bisect_right(self._before, i) - 1
        entry = self._entries[idx]
        timestamps, values = self._decode(idx, entry, with_values=True)
        if timestamps is None:
            raise TsFormatError("下标 %r 落在坏块里" % index)
        k = i - self._before[idx]
        self._reads += 1
        return (timestamps[k], values[k])

    def find(self, ts):
        """块头二分定位；重复时间戳取最早；全都小于返回 -1。"""
        j = bisect.bisect_left(self._good_last, ts)
        while j < len(self._good_idx):
            idx = self._good_idx[j]
            entry = self._entries[idx]
            timestamps, _ = self._decode(idx, entry, with_values=False)
            if timestamps is not None:
                k = bisect.bisect_left(timestamps, ts)
                if k < len(timestamps):
                    self._reads += 1
                    return self._before[idx] + k
            j += 1
        base = self._count - len(self._pending)
        for k, (cur, _) in enumerate(self._pending):
            if cur >= ts:
                self._reads += 1
                return base + k
        self._reads += 1
        return -1

    def __iter__(self):
        """按写入顺序流式读出，一次只解一块，坏块跳过。"""
        for idx in self._good_idx:
            entry = self._entries[idx]
            timestamps, values = self._decode(idx, entry, with_values=True)
            if timestamps is None:
                continue
            for k in range(entry.count):
                self._reads += 1
                yield (timestamps[k], values[k])
        for pair in self._pending:
            self._reads += 1
            yield pair

    def read_all(self):
        return list(self)

    def __len__(self):
        return self._count

    # ---- 元信息 ----

    @property
    def path(self):
        return self._path

    @property
    def last_ts(self):
        return self._anchor_ts()

    @property
    def block_size(self):
        return self._block_size

    def stats(self):
        return {
            "records": self._count,
            "bytes_on_disk": os.fstat(self._fh.fileno()).st_size,
            "appends": self._appends,
            "reads": self._reads,
            "decoded_blocks": self._decoded_blocks,
            "bad_blocks": self._bad_blocks,
            "block_size": self._block_size,
        }

    def close(self):
        """尾块落盘并关闭，可重复调用。"""
        if self._fh is not None and not self._fh.closed:
            try:
                self._flush()
                self._fh.flush()
            finally:
                self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    # ---- 解码 ----

    def _decode(self, idx, entry, with_values):
        """解一个块，返回 (时间戳列表, 值列表)；坏块返回 (None, None)。"""
        if entry.bad:
            return None, None
        self._fh.seek(entry.offset + BLOCK_HEADER.size)
        payload = self._fh.read(entry.payload_len)
        try:
            result = decode_payload(
                entry.base_ts, payload, entry.count, with_values
            )
        except ValueError:
            self._mark_bad(idx)
            return None, None
        self._decoded_blocks += 1
        return result
