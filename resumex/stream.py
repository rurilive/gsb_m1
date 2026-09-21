"""把上游的记录按批推给下游。

来源与下游都是注入的内存对象，用来顶替真实 IO。搬运器逐批取数、
推送，并把进度记在内存里：推了多少条、走到哪个序号、推了几批。
"""

import time


class Record:
    """一条待搬运的记录。

    seq: 记录序号，从 1 开始，比较水位时以它为准。
    payload: 载荷，原样透传给下游。
    """

    __slots__ = ("seq", "payload")

    def __init__(self, seq, payload):
        self.seq = seq
        self.payload = payload

    def __repr__(self):
        return "Record(seq=%r, payload=%r)" % (self.seq, self.payload)

    def __eq__(self, other):
        if not isinstance(other, Record):
            return NotImplemented
        return self.seq == other.seq and self.payload == other.payload


class MemorySource:
    """内存来源，模拟一个能按序号区间查询的上游。

    records: 可迭代的 (seq, payload) 对，序号须严格递增。
    """

    def __init__(self, records=()):
        self._entries = []  # [(seq, payload), ...]
        for seq, payload in records:
            self.append(seq, payload)

    def append(self, seq, payload):
        """追加一条记录，序号必须大于已有的最大序号。"""
        if self._entries and seq <= self._entries[-1][0]:
            raise ValueError("seq must be strictly increasing")
        self._entries.append((seq, payload))

    def fetch(self, after_seq, limit):
        """取序号大于 after_seq 的至多 limit 条，按序号递增返回记录列表。"""
        if limit < 1:
            raise ValueError("limit must be >= 1")
        out = []
        for seq, payload in self._entries:
            if seq > after_seq:
                out.append(Record(seq, payload))
                if len(out) == limit:
                    break
        return out

    @property
    def latest_seq(self):
        """已有记录的最大序号，空时返回 0。"""
        return self._entries[-1][0] if self._entries else 0

    def __len__(self):
        return len(self._entries)


class MemorySink:
    """内存下游，模拟接收推送的外部系统。

    收到的记录按到达顺序留档，watermark 是收到的最大序号。
    """

    def __init__(self):
        self._received = []
        self._watermark = 0
        self._batches = 0

    def push(self, records):
        """接收一批记录，返回接收后的水位。"""
        self._batches += 1
        for record in records:
            self._received.append(record)
            if record.seq > self._watermark:
                self._watermark = record.seq
        return self._watermark

    @property
    def watermark(self):
        return self._watermark

    def received(self):
        """按到达顺序返回已收到记录的快照，新列表，调用方随便改。"""
        return list(self._received)

    def stats(self):
        """计数快照，返回独立 dict。"""
        return {
            "batches": self._batches,
            "received": len(self._received),
            "watermark": self._watermark,
        }


class StreamRunner:
    """把来源记录按批推给下游。

    source: 提供 fetch(after_seq, limit) 的来源。
    sink: 提供 push(records) 的下游。
    batch_size: 每批最多推送的记录条数。
    clock: 注入时钟，用于给进度打时间戳。
    """

    def __init__(self, source, sink, batch_size=2, clock=time.monotonic):
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self._source = source
        self._sink = sink
        self._batch_size = batch_size
        self._clock = clock
        self._last_seq = 0
        self._pushed = 0
        self._batches = 0
        self._last_at = None

    def run(self):
        """逐批取数并推送，直到来源没有新记录，返回本次推送的记录条数。"""
        moved = 0
        while True:
            batch = self._source.fetch(self._last_seq, self._batch_size)
            if not batch:
                break
            self._sink.push(batch)
            self._last_seq = batch[-1].seq
            moved += len(batch)
            self._pushed += len(batch)
            self._batches += 1
            self._last_at = self._clock()
        return moved

    def progress(self):
        """进度快照，返回独立 dict，调用方随便改。"""
        return {
            "last_seq": self._last_seq,
            "pushed": self._pushed,
            "batches": self._batches,
            "last_at": self._last_at,
        }
