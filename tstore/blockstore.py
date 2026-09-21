"""块压缩存储：新文件的实现，与裸存 TsStore 同一套行为。

文件 = 8 字节魔数头 + 若干压缩块（块内布局见 blocks.py）。打开时只
顺序扫一遍块头建立内存索引（偏移、条数、首末时间），不解码负载，
不把整库读进内存；校验不过或截断的块记进 bad_blocks 跳过，其余块
照常读写。追加先攒在内存里，凑够一块才编码落盘，close 时把不足
一块的尾巴也落盘；同一句柄上没落盘的追加立刻可读。
"""

import bisect
import os

from .blocks import BLOCK_HEADER, check_crc, decode_block, encode_block
from .errors import OutOfOrderError, TsFormatError

#: 块压缩文件的魔数头，正好 8 字节。
BLK_MAGIC = b"TSBLK01\n"

#: 新文件的默认块大小（条）。
DEFAULT_BLOCK_SIZE = 256


class BlockStore:
    """块压缩格式的时间点序列。path 不存在或为空就新建。"""  # 行为对齐 TsStore

    def __init__(self, path, block_size=DEFAULT_BLOCK_SIZE):
        if isinstance(block_size, bool) or not isinstance(block_size, int):
            raise TypeError("块大小必须是 int，收到 %r" % type(block_size).__name__)
        if block_size < 1:
            raise ValueError("块大小必须为正，收到 %r" % block_size)
        self._path = str(path)
        self._block_size = block_size
        self._appends = 0
        self._reads = 0
        self._blocks_decoded = 0
        self._pending = []
        self._cache_index = None
        self._cache_pairs = None
        self._fh = None
        try:
            if os.path.exists(self._path) and os.path.getsize(self._path) > 0:
                self._fh = open(self._path, "r+b")
                self._fh.seek(0)
                if self._fh.read(len(BLK_MAGIC)) != BLK_MAGIC:
                    raise TsFormatError("文件头魔数不匹配，不是 tstore 块压缩文件")
            else:
                self._fh = open(self._path, "w+b")
                self._fh.write(BLK_MAGIC)
                self._fh.flush()
            self._scan()
        except Exception:
            self.close()
            raise

    def _scan(self):
        """只读块头建索引；坏块记序号后跳过，截断的尾巴同样记坏。"""
        self._blocks = []  # (偏移, 条数, 基准时间, 末条时间, 负载长度)
        self._starts = []  # 每块第一条的全局下标
        self._lasts = []   # 每块末条时间，供 find 二分
        self._bad_blocks = []
        self._count = 0
        self._fh.seek(0, os.SEEK_END)
        size = self._fh.tell()
        offset = len(BLK_MAGIC)
        seq = 0
        while offset < size:
            self._fh.seek(offset)
            header = self._fh.read(BLOCK_HEADER.size)
            if len(header) < BLOCK_HEADER.size:
                self._bad_blocks.append(seq)
                break
            base, last, count, plen, _ = BLOCK_HEADER.unpack(header)
            payload = self._fh.read(min(plen, size - offset - BLOCK_HEADER.size))
            if len(payload) < plen or not check_crc(header, payload):
                self._bad_blocks.append(seq)
            else:
                self._starts.append(self._count)
                self._lasts.append(last)
                self._blocks.append((offset, count, base, last, plen))
                self._count += count
            offset += BLOCK_HEADER.size + plen
            seq += 1
        self._bytes_on_disk = size
        self._last_ts = self._blocks[-1][3] if self._blocks else None

    # ---- 写入 ----

    def append(self, ts, value):
        """追加一条。时间戳小于上一条时抛 OutOfOrderError。"""
        self._check_pair(ts, value)
        if self._last_ts is not None and ts < self._last_ts:
            raise OutOfOrderError(
                "时间戳 %r 小于上一条 %r，拒绝写入" % (ts, self._last_ts)
            )
        self._pending.append((ts, value))
        self._last_ts = ts
        self._appends += 1
        if len(self._pending) >= self._block_size:
            self._flush_pending()

    def append_many(self, pairs):
        """整批追加；任何一条不合法整批拒绝，文件一个字节都不动。"""
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
            self._pending.append((ts, value))
            self._last_ts = ts
            self._appends += 1
            if len(self._pending) >= self._block_size:
                self._flush_pending()

    @staticmethod
    def _check_pair(ts, value):
        if isinstance(ts, bool) or not isinstance(ts, int):
            raise TypeError("时间戳必须是 int，收到 %r" % type(ts).__name__)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("值必须是 int 或 float，收到 %r" % type(value).__name__)

    def _flush_pending(self):
        if not self._pending:
            return
        blob = encode_block(self._pending)
        self._fh.seek(0, os.SEEK_END)
        self._fh.write(blob)
        self._fh.flush()
        self._starts.append(self._count)
        self._lasts.append(self._pending[-1][0])
        self._blocks.append(
            (
                self._bytes_on_disk,
                len(self._pending),
                self._pending[0][0],
                self._pending[-1][0],
                len(blob) - BLOCK_HEADER.size,
            )
        )
        self._count += len(self._pending)
        self._bytes_on_disk += len(blob)
        self._pending = []

    # ---- 读取 ----

    def _load_block(self, block_index):
        """解出一块，缓存最近一块；只在这里累计解块数。"""
        if self._cache_index == block_index:
            return self._cache_pairs
        offset, count, base, _, plen = self._blocks[block_index]
        self._fh.seek(offset + BLOCK_HEADER.size)
        pairs = decode_block(base, count, self._fh.read(plen))
        self._blocks_decoded += 1
        self._cache_index = block_index
        self._cache_pairs = pairs
        return pairs

    def read_at(self, index):
        """按下标读一条，只解所在块；支持负数下标，越界抛 IndexError。"""
        total = self._count + len(self._pending)
        i = index + total if index < 0 else index
        if i < 0 or i >= total:
            raise IndexError("下标 %r 越界（共 %d 条）" % (index, total))
        self._reads += 1
        if i >= self._count:
            return self._pending[i - self._count]
        block_index = bisect.bisect_right(self._starts, i) - 1
        return self._load_block(block_index)[i - self._starts[block_index]]

    def find(self, ts):
        """第一个时间戳不小于 ts 的下标；全都小于 ts 时返回 -1。

        先在块头的末条时间上二分定位块，只解那一块；重复时间戳返回
        整段里最早的那条。
        """
        block_index = bisect.bisect_left(self._lasts, ts)
        if block_index < len(self._blocks):
            for k, (cur, _) in enumerate(self._load_block(block_index)):
                if cur >= ts:
                    self._reads += 1
                    return self._starts[block_index] + k
        for k, (cur, _) in enumerate(self._pending):
            if cur >= ts:
                self._reads += 1
                return self._count + k
        self._reads += 1
        return -1

    def __iter__(self):
        """按写入顺序流式迭代，一块一块解，不把整库读进内存。"""
        for block_index in range(len(self._blocks)):
            for pair in self._load_block(block_index):
                self._reads += 1
                yield pair
        for pair in self._pending:
            self._reads += 1
            yield pair

    def read_all(self):
        """读出全部记录，返回 (时间戳, 值) 列表。"""
        return list(self)

    def __len__(self):
        return self._count + len(self._pending)

    # ---- 元信息 ----

    @property
    def path(self):
        """文件路径。"""
        return self._path

    @property
    def last_ts(self):
        """最后一条的时间戳，空库返回 None。"""
        return self._last_ts

    def stats(self):
        """计数快照，返回新字典。"""
        return {
            "records": self._count + len(self._pending),
            "bytes_on_disk": self._bytes_on_disk,
            "appends": self._appends,
            "reads": self._reads,
            "blocks_decoded": self._blocks_decoded,
            "bad_blocks": list(self._bad_blocks),
        }

    def close(self):
        """把不足一块的尾巴落盘，刷盘并关闭，可重复调用。"""
        if self._fh is not None and not self._fh.closed:
            self._flush_pending()
            self._fh.flush()
            self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
