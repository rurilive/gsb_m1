"""既有的逐条投递通道。

读到一条 data 或 ddl 就立刻交给下游，begin 与 commit 只计数不投递。
不认事务边界，也不管位点是否重复或乱序，来什么投什么。
"""


class StreamRelay:
    """把事件逐条送往下游的搬运器。"""

    def __init__(self, reader, sink):
        self.reader = reader
        self.sink = sink
        self.events_read = 0
        self.txns_opened = 0
        self.pushed = 0

    def pump(self, max_events=None):
        """读一条投一条，直到流末或读满 max_events 条。

        返回本次投给下游的变更条数。
        """
        pushed = 0
        while max_events is None or self.events_read < max_events:
            event = self.reader.read_event()
            if event is None:
                break
            self.events_read += 1
            if event.kind == "begin":
                self.txns_opened += 1
                continue
            if event.kind == "commit":
                continue
            self.sink.apply([event.as_change()])
            pushed += 1
            self.pushed += 1
        return pushed

    def stats(self):
        return {
            "events_read": self.events_read,
            "txns_opened": self.txns_opened,
            "pushed": self.pushed,
        }

    def __repr__(self):
        return "StreamRelay(events_read=%d, pushed=%d)" % (
            self.events_read, self.pushed)
