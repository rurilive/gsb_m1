"""分段存储引擎。

写入先进活动段；活动段写满 segment_limit 个 key 就滚出一段新的，
老的那段封住不动。查询从最新往旧扫，同一个 key 取最新的段里的值。

压缩目前只有手动入口 compact_once()：挑当前最小的两段并成一段，
一次调用少一段。并出来的结果沿用最新输入那一段的 sid 和 seq，
段与段之间的新旧关系不会因为合并而变化。

落盘都从 device 走账：前台写读走 charge，同步等设备空出来；压缩把
整轮 IO 一次 reserve 在设备上，前台再来的请求就得排队等。打开 Store
时把段读回内存，恢复动作不计账。

meta 文档存在后端里，记 next_sid、next_seq、活动段 id 和段清单；
每次滚段、合并都会重写它。重新 new 一个 Store 读同一份后端，
就是进程重启后的样子。
"""

from .backend import MemoryBackend
from .device import SimDevice
from .segment import Segment, merge_pairs

DEFAULT_SEGMENT_LIMIT = 8


class CompactReport:
    """一次合并的账。"""

    __slots__ = ("inputs", "sid", "seq", "units", "elapsed")

    def __init__(self, inputs, sid, seq, units, elapsed):
        self.inputs = tuple(inputs)
        self.sid = sid
        self.seq = seq
        self.units = units
        self.elapsed = elapsed

    def __repr__(self):
        return "CompactReport(inputs=%r, sid=%r, units=%d, elapsed=%.1f)" % (
            self.inputs, self.sid, self.units, self.elapsed)


class Store:
    """分段存储。

    backend: 段落后端，默认开一个进程内的 MemoryBackend。
    device: IO 设备兼模型时钟，默认开一个 SimDevice。
    segment_limit: 活动段装多少个 key 之后滚新段。
    """

    def __init__(self, backend=None, device=None, segment_limit=DEFAULT_SEGMENT_LIMIT):
        if segment_limit < 1:
            raise ValueError("segment_limit must be positive")
        self.backend = MemoryBackend() if backend is None else backend
        self.device = SimDevice() if device is None else device
        self.segment_limit = segment_limit
        self._segments = {}
        self._meta = self._load_meta()

    # ---------- 打开与落盘 ----------

    def _load_meta(self):
        """把后端里的 meta 和段读进来，没有就开一份空的。"""
        meta = self.backend.load_meta()
        if meta is None:
            meta = {"next_sid": 0, "next_seq": 0, "active": None, "segments": []}
        self._segments = {}
        for row in meta["segments"]:
            seg = Segment(
                row["sid"],
                self.backend.read_segment(row["sid"]),
                seq=row["seq"],
                created=row["created"],
            )
            self._segments[seg.sid] = seg
        return meta

    def _save_meta(self, background=False):
        """把段清单写回 meta，返回这次写盘的完成时刻。

        background=True 走 reserve，占住设备但不推进前台时钟。
        """
        rows = [
            {"sid": seg.sid, "seq": seg.seq, "created": seg.created}
            for seg in self.segments()
        ]
        self._meta["segments"] = rows
        self.backend.save_meta(self._meta)
        if background:
            return self.device.reserve("write", 1)
        return self.device.charge("write", 1)

    # ---------- 视图 ----------

    def segments(self):
        """现存的所有段，按 (seq, sid) 升序，越靠后越新。"""
        return sorted(self._segments.values(), key=lambda s: s.order)

    @property
    def active(self):
        """当前可写的活动段，可能还没有。"""
        sid = self._meta["active"]
        return None if sid is None else self._segments.get(sid)

    def snapshot(self):
        """当前全量视图，最新的值赢。调试与对拍用，不记 IO。"""
        values = {}
        for seg in self.segments():
            values.update(dict(seg.items))
        return values

    # ---------- 读写 ----------

    def put(self, key, value):
        """写一条数据进活动段，返回这次前台写的耗时。"""
        if key is None:
            raise ValueError("key must not be None")
        started = self.device.now()
        active = self.active
        if active is None or active.size >= self.segment_limit:
            active = self._rotate()
        pairs = [(k, v) for k, v in active.items if k != key]
        pairs.append((key, value))
        seg = Segment(active.sid, pairs, seq=active.seq, created=active.created)
        self._segments[seg.sid] = seg
        self.backend.write_segment(seg.sid, seg.as_pairs())
        end = self.device.charge("write", 1)
        return end - started

    def get(self, key):
        """查一个 key，取最新的段里的值，查不到返回 None。"""
        self.device.charge("read", 1)
        for seg in reversed(self.segments()):
            if key in seg:
                return seg.lookup(key)
        return None

    def _rotate(self):
        """封住当前活动段，开一段新的。"""
        sid = self._meta["next_sid"]
        seq = self._meta["next_seq"]
        self._meta["next_sid"] = sid + 1
        self._meta["next_seq"] = seq + 1
        seg = Segment(sid, [], seq=seq, created=self.device.now())
        self._segments[sid] = seg
        self.backend.write_segment(sid, [])
        self.device.charge("write", 1)
        self._meta["active"] = sid
        self._save_meta()
        return seg

    # ---------- 压缩 ----------

    def compact_once(self):
        """手动压缩一轮：挑最小的两段并成一段，少于两段就返回 None。

        整轮合并的 IO 一次占住设备，前台写要等它让出来。
        """
        picked = self._candidates(2)
        if len(picked) < 2:
            return None
        return self._merge(picked)

    def _candidates(self, n):
        """够格压缩的段：活动段不算，按 (size, seq, sid) 升序取前 n 个。"""
        active = self._meta["active"]
        pool = [s for s in self.segments() if s.sid != active]
        pool.sort(key=lambda s: (s.size, s.seq, s.sid))
        return pool[:n]

    def _merge(self, picked):
        """把这几段并成一段，结果顶掉最新输入那一段的身份。

        整轮 IO 一次 reserve 在设备上：reads 的单位数是输入段之和，写是
        结果段的大小，另外还有一个单位写 meta。占设备不推进前台时钟，
        前台写撞上这段占用就得排队。
        """
        started = self.device.now()
        inputs = sorted(picked, key=lambda s: s.order)
        newest = inputs[-1]
        read_units = sum(s.size for s in inputs)
        self.device.reserve("read", read_units)
        blobs = [self.backend.read_segment(s.sid) for s in inputs]
        pairs = merge_pairs(blobs)

        self.device.reserve("write", len(pairs))
        self.backend.write_segment(newest.sid, pairs)
        for seg in inputs[:-1]:
            self.backend.drop_segment(seg.sid)
            del self._segments[seg.sid]
        merged = Segment(newest.sid, pairs, seq=newest.seq, created=newest.created)
        self._segments[merged.sid] = merged
        end = self._save_meta(background=True)
        units = read_units + len(pairs) + 1
        return CompactReport([s.sid for s in inputs], merged.sid, merged.seq, units, end - started)

    def __repr__(self):
        return "Store(segments=%d, active=%r, limit=%d)" % (
            len(self._segments), self._meta["active"], self.segment_limit)
