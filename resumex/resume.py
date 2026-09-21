"""双源合流搬运：水位落盘续传、乱序窗口与分路背压。

设计要点：

* 每个来源（route）各自维护一个已确认序号，追加写入同一个带校验和的
  水位日志；重启回放得到同一份进度，各从自己的水位之后取数。
* 全局水位是两路确认序号的最大值。低于全局水位的记录：落在
  ``global - window`` 之内算迟到抖动，补进给下游；超出窗口的丢弃。
* 水位日志每行一条、自带 HMAC 校验和。加载时只认到第一个坏行为止，
  坏尾巴截掉，进度退回日志里最后一个完好点，而不是整份作废。
* 背压按路判断：某路下游阻塞时只跳过该路，另一路照常取数推送。
"""

import hashlib
import hmac
import os
import time
from collections import deque

from resumex.stream import MemorySink


_VERSION = "rx1"
_SECRET = b"resumex-watermark-v1"


class WatermarkStore:
    """追加式双源水位日志，每行自带校验和。

    path: 水位文件路径。
    routes: 路名可迭代对象，加载时用于校验日志里的路名。
    clock: 注入时钟，给每条水位打时间戳。

    文件的每一行形如 ``rx1|<route>|<seq>|<ts>|<mac>``。半截写入、
    校验和不符等损坏行都不是有效值；加载在第一个坏行处停止并截断，
    之后新的水位从最后一个完好点继续追加。
    """

    def __init__(self, path, routes=(), clock=time.monotonic):
        self._path = path
        self._clock = clock
        self._positions = {name: 0 for name in routes}
        self._repairs = 0
        self._bad_lines = 0
        self._commits = 0
        self._load()

    @staticmethod
    def _digest(route, seq, timestamp):
        message = ("%s|%s|%d|%s" % (_VERSION, route, seq, timestamp)).encode("utf-8")
        return hmac.new(_SECRET, message, hashlib.sha256).hexdigest()

    @staticmethod
    def _parse_line(line, routes):
        """解析并校验一行，成功返回 (route, seq)，否则返回 None。"""
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if not text.endswith("\n"):
            return None
        parts = text.rstrip("\n").split("|")
        if len(parts) != 5 or parts[0] != _VERSION:
            return None
        route, seq_text, timestamp, mac = parts[1:]
        if routes and route not in routes:
            return None
        try:
            seq = int(seq_text)
        except ValueError:
            return None
        if seq < 0 or not timestamp or not mac:
            return None
        expected = WatermarkStore._digest(route, seq, timestamp)
        if not hmac.compare_digest(mac, expected):
            return None
        return route, seq

    def _load(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "rb") as handle:
            raw = handle.read()
        valid_end = 0
        for line in raw.splitlines(keepends=True):
            parsed = self._parse_line(line, self._positions)
            if parsed is None:
                self._bad_lines += 1
                break
            route, seq = parsed
            self._positions[route] = seq
            valid_end += len(line)
        if valid_end != len(raw):
            with open(self._path, "wb") as handle:
                handle.write(raw[:valid_end])
                handle.flush()
                os.fsync(handle.fileno())
            self._repairs += 1

    def position(self, route):
        """某一路的当前确认序号，未知路返回 0。"""
        return self._positions.get(route, 0)

    def commit(self, route, seq):
        """确认某路推进到 seq：追加一条完好水位并刷盘。"""
        timestamp = repr(self._clock())
        mac = self._digest(route, seq, timestamp)
        line = "%s|%s|%d|%s|%s\n" % (_VERSION, route, seq, timestamp, mac)
        directory = os.path.dirname(os.path.abspath(self._path))
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(self._path, "ab") as handle:
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        self._positions[route] = seq
        self._commits += 1

    def stats(self):
        """日志健康度快照。"""
        return {
            "commits": self._commits,
            "repairs": self._repairs,
            "bad_lines": self._bad_lines,
        }


class BackpressureSink(MemorySink):
    """可模拟背压的下游：阻塞期间拒入，且按路各自一个实例。"""

    def __init__(self):
        super().__init__()
        self._blocked = False

    def set_blocked(self, blocked):
        """True 时该路停推（取数随之停在上个水位），False 恢复。"""
        self._blocked = blocked

    @property
    def blocked(self):
        return self._blocked

    def offer(self, records):
        """非阻塞时照 push 接收并返回 True；阻塞时不接收并返回 False。"""
        if self._blocked:
            return False
        self.push(records)
        return True


class _OrderGate:
    """乱序窗口判定：迟到补入、超窗丢弃、窗口内去重。"""

    def __init__(self, positions, window):
        if window < 0:
            raise ValueError("window must be >= 0")
        self._positions = positions
        self._window = window
        self._recent = deque()
        self._recent_set = set()

    def plan(self, batch):
        """判一批记录，返回 (accepted, stats)，不改变自身状态。"""
        global_mark = max(self._positions.values()) if self._positions else 0
        floor = global_mark - self._window
        accepted = []
        late = 0
        dropped = 0
        duplicates = 0
        seen = set()
        for record in batch:
            seq = record.seq
            if seq > global_mark:
                accepted.append(record)
            elif seq in self._recent_set or seq in seen:
                duplicates += 1
            elif seq >= floor:
                accepted.append(record)
                late += 1
                seen.add(seq)
            else:
                dropped += 1
        return accepted, {"late_accepted": late, "dropped": dropped, "duplicates": duplicates}

    def commit(self, batch):
        """推送成功后登记本批序号并裁剪窗口外的去重记忆。"""
        global_mark = max(self._positions.values()) if self._positions else 0
        floor = global_mark - self._window
        for record in batch:
            seq = record.seq
            if seq in self._recent_set:
                continue
            self._recent.append(seq)
            self._recent_set.add(seq)
        while self._recent and self._recent[0] < floor:
            self._recent_set.discard(self._recent.popleft())


class MergedStreamRunner:
    """双源合流搬运器：分路落盘续传、乱序窗口、分路背压。

    sources: {route: source}，source 提供 fetch(after_seq, limit)。
    sinks: {route: sink}，sink 提供 offer(records)（如 BackpressureSink）；
           普通 MemorySink 也可，按永不阻塞处理。
    store: WatermarkStore 实例，或水位文件路径字符串（自动建 store）。
    batch_size: 每路每轮最多取多少条。
    window: 乱序窗口大小，序号低于全局水位超过它的记录丢弃。
    clock: 注入时钟，透传给自动创建的 WatermarkStore。
    """

    def __init__(self, sources, sinks, store, batch_size=2, window=5, clock=time.monotonic):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if not sources:
            raise ValueError("at least one source is required")
        if set(sources) != set(sinks):
            raise ValueError("sources and sinks must use the same routes")
        self._routes = tuple(sources)
        self._sources = sources
        self._sinks = sinks
        self._batch_size = batch_size
        if isinstance(store, str):
            store = WatermarkStore(store, self._routes, clock=clock)
        self._store = store
        self._gate = _OrderGate(
            {route: store.position(route) for route in self._routes}, window
        )
        self._window = window
        self._pushed = 0
        self._batches = 0
        self._late = 0
        self._dropped = 0
        self._duplicates = 0
        self._blocked = {route: 0 for route in self._routes}

    def _offer(self, route, records):
        sink = self._sinks[route]
        offer = getattr(sink, "offer", None)
        if offer is not None:
            return offer(records)
        sink.push(records)
        return True

    def _is_blocked(self, route):
        sink = self._sinks[route]
        check = getattr(sink, "blocked", None)
        if callable(check):
            return bool(check())
        return check is True

    def run(self):
        """轮转两路各推一轮，直到一轮内没有任何路取得进展，返回推送条数。"""
        total_moved = 0
        while True:
            progressed = False
            for route in self._routes:
                if self._is_blocked(route):
                    self._blocked[route] += 1
                    continue
                positions = {
                    name: self._store.position(name) for name in self._routes
                }
                self._gate._positions = positions
                batch = self._sources[route].fetch(
                    self._store.position(route), self._batch_size
                )
                if not batch:
                    continue
                accepted, verdict = self._gate.plan(batch)
                if accepted and not self._offer(route, accepted):
                    self._blocked[route] += 1
                    continue
                self._gate.commit(batch)
                self._store.commit(route, batch[-1].seq)
                self._pushed += len(accepted)
                self._batches += 1
                self._late += verdict["late_accepted"]
                self._dropped += verdict["dropped"]
                self._duplicates += verdict["duplicates"]
                total_moved += len(accepted)
                progressed = True
            if not progressed:
                break
        return total_moved

    def progress(self):
        """进度与乱序/背压计数快照。"""
        positions = {route: self._store.position(route) for route in self._routes}
        return {
            "positions": positions,
            "global_watermark": max(positions.values()) if positions else 0,
            "window": self._window,
            "pushed": self._pushed,
            "batches": self._batches,
            "late_accepted": self._late,
            "dropped": self._dropped,
            "duplicates": self._duplicates,
            "blocked": dict(self._blocked),
        }
