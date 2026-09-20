"""解析结果的接收端。

MultipartParser 不保存正文,内容按到达的块推给 sink:
PartCollector 把内容攒进内存,给测试和小表单用;DiscardSink
只记账,大文件或压测时用。
"""


class Part:
    """解析出来的一个部分:头部、参数和正文。"""

    __slots__ = ("headers", "params", "data")

    def __init__(self, headers=None, params=None, data=b""):
        self.headers = dict(headers or {})
        self.params = dict(params or {})
        self.data = data

    @property
    def name(self):
        """表单字段名,没有就是 None。"""
        return self.params.get("name")

    @property
    def filename(self):
        """文件名参数,没有就是 None。"""
        return self.params.get("filename")

    def __repr__(self):
        return "Part(name=%r, filename=%r, %d bytes)" % (
            self.name,
            self.filename,
            len(self.data),
        )

    def __eq__(self, other):
        if not isinstance(other, Part):
            return NotImplemented
        return (
            self.headers == other.headers
            and self.params == other.params
            and self.data == other.data
        )

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


class PartCollector:
    """把正文收进内存,结束后用 parts() 取整份结果。

    begin_part 之前一个部分还没 end_part 的话,先把它当结束收掉。
    """

    def __init__(self):
        self._parts = []
        self._cur = None

    def begin_part(self, headers, params):
        if self._cur is not None:
            self._parts.append(self._cur)
        self._cur = Part(headers, params, bytearray())

    def write(self, data):
        if self._cur is None:
            raise RuntimeError("write before begin_part")
        self._cur.data += data

    def end_part(self):
        if self._cur is None:
            raise RuntimeError("end_part without an open part")
        self._cur.data = bytes(self._cur.data)
        self._parts.append(self._cur)
        self._cur = None

    def parts(self):
        return list(self._parts)


class DiscardSink:
    """只记账不留内容:部分的个数、字节数、字段名。"""

    def __init__(self):
        self.parts = 0
        self.bytes_in = 0
        self.names = []

    def begin_part(self, headers, params):
        self.parts += 1
        self.names.append(params.get("name"))

    def write(self, data):
        self.bytes_in += len(data)

    def end_part(self):
        pass
