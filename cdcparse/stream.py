"""事件源与逐条读取器。

来源只负责按到达顺序吐出一行行文本，读多久、怎么读由读取器决定。
"""

from cdcparse.events import ParseError, parse_line


class MemorySource:
    """内存事件源：一组已经写好的 JSON 行。

    迭代时按给定顺序产出，不排序、不去重、不改写。
    每次 for 都会拿到一份新的快照迭代器，可以重复回放同一份内容。
    """

    def __init__(self, lines=()):
        self._lines = list(lines)

    def __iter__(self):
        return iter(list(self._lines))

    def append(self, line):
        self._lines.append(line)

    def lines(self):
        """当前内容的浅拷贝。"""
        return list(self._lines)

    def __len__(self):
        return len(self._lines)

    def __repr__(self):
        return "MemorySource(lines=%d)" % len(self._lines)


class FileSource:
    """日志文件事件源：按行读文件。

    空行跳过；末尾没有换行的残行也照样产出，交给读取器判断。
    """

    def __init__(self, path):
        self.path = path

    def __iter__(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                text = line.rstrip("\n")
                if text.strip():
                    yield text

    def __repr__(self):
        return "FileSource(%r)" % (self.path,)


class EventReader:
    """逐条读取事件的读取器。

    read_event() 每次返回一个 Event，读到流末返回 None。
    事件按来源的到达顺序返回，位点取自事件自身，读取器不做排序。
    行内容坏了抛 ParseError，错误信息带行号。
    """

    def __init__(self, source):
        self._source = iter(source)
        self._lookahead = None
        self.arrivals = 0
        self.position = 0

    def _pull(self):
        if self._lookahead is None:
            try:
                self._lookahead = next(self._source)
            except StopIteration:
                return None
        line = self._lookahead
        self._lookahead = None
        return line

    def read_event(self):
        line = self._pull()
        if line is None:
            return None
        self.arrivals += 1
        try:
            event = parse_line(line)
        except ParseError as exc:
            raise ParseError("第 %d 行: %s" % (self.arrivals, exc))
        self.position = event.pos
        return event

    def read_all(self):
        """把剩下的行全部读成事件列表；中途有坏行照样抛 ParseError。"""
        events = []
        while True:
            event = self.read_event()
            if event is None:
                return events
            events.append(event)

    def at_end(self):
        """来源是否已经不再有下一行（不会消费下一行）。"""
        if self._lookahead is not None:
            return False
        try:
            self._lookahead = next(self._source)
        except StopIteration:
            return True
        return False

    def __repr__(self):
        return "EventReader(arrivals=%d, position=%d)" % (
            self.arrivals, self.position)
