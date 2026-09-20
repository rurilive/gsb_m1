"""按块喂入的定长记录解码器。

来源怎么切块是来源的自由：记录可能跨块，一块里也可能挤着好几条记录。
RecordStream 只保留凑不满一条记录的尾巴，消费过的字节立刻丢掉。
"""

from wirepack.errors import DecodeError
from wirepack.records import RECORD_SIZE, unpack_record


def chunked(data, size):
    """把一段字节按固定大小切片，最后一块可以不满。"""
    if size <= 0:
        raise ValueError("size 必须为正数: %r" % (size,))
    return [data[i:i + size] for i in range(0, len(data), size)]


class RecordStream:
    """定长记录的流式解码器。

    feed() 吃任意大小的字节块，吐出这次凑齐的记录；
    offset 是已经消费掉的字节数，pending 是还留在缓冲里的字节数。
    """

    def __init__(self):
        self._buf = bytearray()
        self.offset = 0
        self.records = 0

    @property
    def pending(self):
        return len(self._buf)

    def feed(self, chunk):
        """喂一块字节，返回本次解出的记录列表。"""
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("chunk 需要字节串，收到 %r" % (type(chunk).__name__,))
        self._buf += chunk
        out = []
        while len(self._buf) >= RECORD_SIZE:
            try:
                record, _ = unpack_record(self._buf, 0)
            except DecodeError as exc:
                if exc.offset is not None:
                    exc.offset += self.offset
                raise
            del self._buf[:RECORD_SIZE]
            self.offset += RECORD_SIZE
            self.records += 1
            out.append(record)
        return out

    def finish(self):
        """流已经到末尾：缓冲里还剩半个记录就说明尾巴被截断了。"""
        if self._buf:
            raise DecodeError("流末残留 %d 字节，记录被截断" % (len(self._buf),),
                              offset=self.offset, field="record")
        return []

    def __repr__(self):
        return "RecordStream(offset=%d, records=%d, pending=%d)" % (
            self.offset, self.records, len(self._buf))


def iter_records(chunks):
    """把一串字节块解成记录序列，流末校验尾巴。"""
    stream = RecordStream()
    for chunk in chunks:
        for record in stream.feed(chunk):
            yield record
    for record in stream.finish():
        yield record
