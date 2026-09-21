"""双源续传：水位落盘、迟到窗口合并、分路背压。

两路来源（A/B）各推各的同一路行情流，同一支标的的更新可能落在
任意一边。本模块在 StreamRunner 之外提供三件套：

- WatermarkStore：水位落盘。主文件存最后一次完好快照，旧快照退
  成 .bak；每行带 crc32，半行、坏校验直接判废，整份损坏退回
  .bak 的上一个完好点，绝不从头清零。
- BackpressureGate：下游就绪闸门，每路一个，慢的一路单独停取，
  不牵连另一路。
- MergeRunner：两路按各自水位取数，按全局水位 + 可配窗口判定
  迟到补入 / 超窗丢弃 / 重复不喂，并把分路水位落盘。
"""

import os
import tempfile
import time
import zlib

MAGIC = "resumex-watermark-v1"


class WatermarkStore:
    """分路水位的落盘存储。

    path: 水位文件路径；上一次完好快照保留在 path + ".bak"。
    """

    def __init__(self, path):
        self._path = path
        self._bak = path + ".bak"
        self._positions = {}
        self._stats = {"commits": 0, "rejected_lines": 0, "fallbacks": 0}
        self._last_recovery = None  # ("primary"|"backup"|"fresh", path)
        self._need_restore = False
        self._load()

    # ---- 读取 -------------------------------------------------------

    def get(self, lane, default=0):
        """返回某一路的已确认水位，没有记录时返回 default。"""
        return self._positions.get(lane, default)

    def positions(self):
        """返回 {lane: seq} 的独立快照。"""
        return dict(self._positions)

    def _load(self):
        primary = self._read_file(self._path)
        if primary is not None:
            self._positions = primary[0]
            self._stats["rejected_lines"] += primary[1]
            self._last_recovery = ("primary", self._path)
            return
        backup = self._read_file(self._bak)
        if backup is not None:
            self._positions = backup[0]
            self._stats["rejected_lines"] += backup[1]
            self._stats["fallbacks"] += 1
            self._last_recovery = ("backup", self._bak)
            self._need_restore = True
            return
        self._positions = {}
        if os.path.exists(self._path) or os.path.exists(self._bak):
            self._stats["fallbacks"] += 1
            self._need_restore = True
        self._last_recovery = ("fresh", self._path)

    def _read_file(self, path):
        """读出一份快照，返回 ({lane: seq}, 判废行数)；文件不可用返回 None。"""
        try:
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except (OSError, UnicodeDecodeError):
            return None
        lines = content.split("\n")
        if not lines or lines[0] != MAGIC:
            return None
        out = {}
        rejected = 0
        for line in lines[1:]:
            if not line:
                continue
            parsed = self._parse(line)
            if parsed is None:
                rejected += 1
                continue
            lane, seq = parsed
            out[lane] = seq
        return out, rejected

    @staticmethod
    def _parse(line):
        parts = line.split("|")
        if len(parts) != 3:
            return None
        lane, seq_text, checksum = parts
        if not lane:
            return None
        body = MAGIC + "|" + lane + "|" + seq_text
        if "%08x" % (zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF) != checksum:
            return None
        try:
            seq = int(seq_text)
        except ValueError:
            return None
        if seq < 0:
            return None
        return lane, seq

    # ---- 写入 -------------------------------------------------------

    def commit(self, updates=None, **kwargs):
        """原子落盘当前全部水位。

        主文件退成 .bak，再写入新主文件，任何时刻磁盘上都至少有
        一份完好快照。水位只许前进，倒退的更新会被拒绝。
        """
        merged = dict(self._positions)
        merged.update(updates or {})
        merged.update(kwargs)
        for lane, seq in merged.items():
            if int(seq) < self._positions.get(lane, 0):
                raise ValueError("watermark for %r cannot move backwards" % lane)
            merged[lane] = int(seq)
        directory = os.path.dirname(os.path.abspath(self._path))
        os.makedirs(directory, exist_ok=True)
        if os.path.exists(self._path):
            os.replace(self._path, self._bak)
        fd, tmp = tempfile.mkstemp(prefix=".wm-", dir=directory)
        lines = [MAGIC]
        for lane in sorted(merged):
            body = MAGIC + "|" + lane + "|" + str(merged[lane])
            checksum = "%08x" % (zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF)
            lines.append("%s|%d|%s" % (lane, merged[lane], checksum))
        text = "\n".join(lines) + "\n"
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        self._positions = merged
        self._stats["commits"] += 1
        self._need_restore = False

    # ---- 观测 -------------------------------------------------------

    def stats(self):
        """计数快照：commits / rejected_lines / fallbacks。"""
        return dict(self._stats)

    def last_recovery(self):
        """最近一次加载时水位取自哪里：(来源, 路径)。"""
        return self._last_recovery


class BackpressureGate:
    """单路下游的就绪闸门。

    close() 表示下游慢、本路暂停取数；open() 恢复。阻塞轮次、
    阻塞/恢复次数、第一次阻塞的时钟值分开记录，两路各持一个，
    互不牵连。
    """

    def __init__(self, clock=time.monotonic):
        self._open = True
        self._clock = clock
        self._blocked_rounds = 0
        self._block_events = 0
        self._first_blocked_at = None
        self._resume_events = 0

    def ready(self):
        return self._open

    def close(self):
        if self._open:
            self._open = False
            self._block_events += 1
            if self._first_blocked_at is None:
                self._first_blocked_at = self._clock()

    def open(self):
        if not self._open:
            self._open = True
            self._resume_events += 1

    def note_blocked_round(self):
        """runner 每发现一次本路该取而取不了，记一个阻塞轮次。"""
        self._blocked_rounds += 1

    def stats(self):
        return {
            "ready": self._open,
            "blocked_rounds": self._blocked_rounds,
            "block_events": self._block_events,
            "resume_events": self._resume_events,
            "first_blocked_at": self._first_blocked_at,
        }


class MergeRunner:
    """两路来源合并搬运，带落盘续传、迟到窗口与分路背压。

    sources: {lane: source}，source 提供 fetch(after_seq, limit)。
    sink: 提供 push(records) 的下游。
    store: 分路水位的 WatermarkStore，重启后用同一份文件接着推。
    window: 乱序窗口大小 W。seq == global_watermark 或已喂过的
        不重喂；global_watermark - W <= seq < global_watermark 算
        迟到补入；seq < global_watermark - W 超窗丢弃；W=0 时一
        切旧序号丢弃。
    batch_size: 每路每轮至多取数条数。
    gates: {lane: BackpressureGate}，缺省每路自建常开闸门。
    clock: 注入时钟，供闸门记阻塞时刻。
    """

    def __init__(self, sources, sink, store, window=5, batch_size=10,
                 gates=None, clock=time.monotonic):
        if not sources:
            raise ValueError("sources must not be empty")
        if window < 0:
            raise ValueError("window must be >= 0")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self._sources = dict(sources)
        self._sink = sink
        self._store = store
        self._window = window
        self._batch_size = batch_size
        self._clock = clock
        self._gates = dict(gates or {})
        for lane in self._sources:
            if lane not in self._gates:
                self._gates[lane] = BackpressureGate(clock=clock)
        self._global_watermark = max(
            (self._store.get(lane) for lane in self._sources), default=0
        )
        self._delivered = set()
        self._stats = {
            "fetched": {lane: 0 for lane in self._sources},
            "pushed": 0,
            "duplicates": 0,
            "late_accepted": 0,
            "late_dropped": 0,
            "batches": 0,
        }

    def run(self):
        """每轮逐路取数合并推送，直到本轮没有任何一路取到记录。

        闸门关闭的一路跳过取数并记一个阻塞轮次，另一路照跑不误。
        每路批次处理完立刻把该路水位落盘。返回本次喂给下游的条数。
        """
        pushed_this_call = 0
        while True:
            moved_any = False
            for lane, source in self._sources.items():
                gate = self._gates[lane]
                if not gate.ready():
                    gate.note_blocked_round()
                    continue
                position = self._store.get(lane)
                batch = source.fetch(position, self._batch_size)
                if not batch:
                    continue
                moved_any = True
                accepted = self._classify(lane, batch)
                if accepted:
                    self._sink.push(accepted)
                    self._stats["pushed"] += len(accepted)
                    pushed_this_call += len(accepted)
                self._store.commit({lane: batch[-1].seq})
            if not moved_any:
                break
        return pushed_this_call

    def _classify(self, lane, batch):
        """把一路批次分成 喂入 / 迟到补入 / 超窗丢弃 / 重复。"""
        accepted = []
        for record in batch:
            seq = record.seq
            self._stats["fetched"][lane] += 1
            if seq == self._global_watermark or seq in self._delivered:
                self._stats["duplicates"] += 1
                continue
            if seq > self._global_watermark:
                accepted.append(record)
                self._delivered.add(seq)
                self._global_watermark = seq
            elif seq >= self._global_watermark - self._window:
                accepted.append(record)
                self._delivered.add(seq)
                self._stats["late_accepted"] += 1
            else:
                self._stats["late_dropped"] += 1
            floor = self._global_watermark - self._window
            self._delivered = {s for s in self._delivered if s >= floor}
        return accepted

    def global_watermark(self):
        """当前全局水位（顺序视角下已确认的最大序号）。"""
        return self._global_watermark

    def stats(self):
        """计数快照，dict 与每路子 dict 均为独立副本。"""
        stats = dict(self._stats)
        stats["fetched"] = dict(stats["fetched"])
        stats["gates"] = {lane: gate.stats() for lane, gate in self._gates.items()}
        stats["positions"] = self._store.positions()
        stats["global_watermark"] = self._global_watermark
        return stats
