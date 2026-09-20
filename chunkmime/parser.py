"""按块喂入的 multipart/form-data 解析器。

上传网关把网络收到的字节一块块喂进来,这里负责切出表单字段和
文件内容:每个部分的头部先报给 sink,正文按到达的块写下去,部分
结束再报一次。正文不留在解析器手里,大文件可以边收边落盘。
"""

from .headers import parse_header_block, parse_params
from .sink import PartCollector

_PREAMBLE = 0
_HEADERS = 1
_BODY = 2
_DONE = 3


class MultipartParser:
    """按块喂入的 multipart/form-data 解析器。

    用法:

        parser = MultipartParser(boundary, sink)
        for chunk in chunks:
            parser.feed(chunk)
        parser.finish()

    sink 要有 begin_part(headers, params)、write(data)、end_part()
    三个方法,见 sink.py。分隔行按 CRLF 换行,收尾分隔行之后的
    epilogue 忽略;正文不在解析器里缓存,手里只留跨块的分隔行前缀。
    """

    def __init__(self, boundary, sink=None):
        if isinstance(boundary, str):
            boundary = boundary.encode("ascii")
        if not boundary:
            raise ValueError("boundary must not be empty")
        self._boundary = bytes(boundary)
        # 正文里的分隔行,行首那个 CRLF 也算它的
        self._marker = b"\r\n--" + self._boundary
        # 第一个分隔行前面可能没有 CRLF(前导内容为空时)
        self._opening = b"--" + self._boundary
        self._sink = sink if sink is not None else PartCollector()
        self._state = _PREAMBLE
        self._buf = b""
        self._hold = b""
        self._stub = 0
        # 当前有没有还没 end_part 的部分
        self._open = False

    def feed(self, chunk):
        """喂一块字节,内容有多少就处理多少。"""
        if not chunk or self._state is _DONE:
            return
        data = self._buf + chunk
        self._buf = b""
        while data:
            if self._state is _PREAMBLE:
                data = self._eat_preamble(data)
            elif self._state is _HEADERS:
                data = self._eat_headers(data)
            elif self._state is _BODY:
                data = self._eat_body(data)
            else:
                return

    def finish(self):
        """流结束,收尾。"""
        self._state = _DONE
        self._buf = b""
        self._hold = b""

    # ---- 各状态的处理 ----

    def _eat_preamble(self, data):
        if data.startswith(self._opening):
            return self._delim_tail(data[len(self._opening):])
        i = data.find(self._marker)
        if i < 0:
            # 前导内容没用,只留可能是分隔行开头的一小截
            self._buf = self._tail(data)
            return b""
        return self._delim_tail(data[i + len(self._marker):])

    def _eat_headers(self, data):
        if self._hold:
            # 头部跨块:攒齐了再找结束空行
            self._hold += data
            j = self._hold.find(b"\n\r\n")
            if j < 0:
                return b""
            block, rest = self._hold[:j], self._hold[j + 3:]
            self._hold = b""
            return self._begin_part(block, rest)
        # 头部大多整块到齐,先在块里找结束空行
        i = data.find(b"\r\n\r\n")
        if i >= 0:
            return self._begin_part(data[:i], data[i + 4:])
        # 没找到:头部可能被切开了,先攒着
        self._hold = data
        return b""

    def _eat_body(self, data):
        if self._stub:
            # 接着上一块跳完剩下的那几个字节
            n = min(self._stub, len(data))
            self._stub -= n
            if self._stub:
                return b""
            self._state = _HEADERS
            return data[n:]
        i = data.find(self._marker)
        if i >= 0:
            self._sink.write(data[:i])
            return self._delim_tail(data[i + len(self._marker):])
        k = len(self._tail(data))
        if k > 3:
            # 块尾这一截像是分隔行开头,先照分隔行切下来,
            # 后面几个字节等下一块直接跳过
            self._sink.write(data[:-k])
            self._stub = len(self._marker) - k
            return b""
        self._sink.write(data[:-k] if k else data)
        self._buf = data[-k:] if k else b""
        return b""

    def _delim_tail(self, rest):
        """分隔行本体之后:-- 是收尾,CRLF 表示后面还跟着一个部分。"""
        head = rest[:2]
        if head == b"--":
            self._end_part()
            self._state = _DONE
            return rest[2:]
        if head == b"\r\n":
            self._end_part()
            self._state = _HEADERS
            return rest[2:]
        # 这两个字节还没到齐,当前部分先当结束,剩下的留给头部状态
        self._state = _HEADERS
        self._buf = rest
        return b""

    def _begin_part(self, block, rest):
        headers = parse_header_block(block)
        params = parse_params(headers.get("content-disposition", ""))
        self._sink.begin_part(headers, params)
        self._open = True
        self._state = _BODY
        return rest

    def _end_part(self):
        if self._open:
            self._sink.end_part()
            self._open = False

    def _tail(self, data):
        """data 末尾可能是分隔行开头的一截就返回它,否则返回空。"""
        limit = min(len(data), len(self._marker) - 1)
        for k in range(limit, 0, -1):
            if self._marker.startswith(data[-k:]):
                return data[-k:]
        return b""
