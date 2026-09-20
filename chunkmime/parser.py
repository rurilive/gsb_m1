"""按块喂入的 multipart/form-data 解析器。

上传网关把网络收到的字节一块块喂进来,这里负责切出表单字段和
文件内容:每个部分的头部先报给 sink,正文按到达的块写下去,部分
结束再报一次。正文不留在解析器手里,大文件可以边收边落盘。
"""

from .headers import parse_header_block, parse_params
from .errors import ParseError
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
    epilogue 忽略;正文不在解析器里缓存,手里只留跨块的分隔行候选。
    候选后面跟的两个字节(CRLF 或 --)到齐了才算真分隔行,对不上
    的按正文写下去;finish() 时还没看到收尾分隔行就抛 ParseError。
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
        # 还在流的起点:第一个分隔行可以不带前导 CRLF
        self._at_start = True
        # 当前有没有还没 end_part 的部分
        self._open = False

    def feed(self, chunk):
        """喂一块字节,内容有多少就处理多少。"""
        if not chunk or self._state is _DONE:
            return
        self._buf += chunk
        self._process()

    def finish(self):
        """流结束,收尾。收尾分隔行没看全就是流断了,抛 ParseError。"""
        if self._state is not _DONE:
            self._state = _DONE
            self._buf = b""
            raise ParseError("truncated multipart stream")

    # ---- 各状态的处理 ----

    def _process(self):
        # 每个状态处理 self._buf 里能处理的部分;返回 False 表示
        # 剩下的字节不够做判断,等下一块
        while self._state is not _DONE:
            if self._state is _PREAMBLE:
                if not self._eat_preamble():
                    break
            elif self._state is _HEADERS:
                if not self._eat_headers():
                    break
            elif not self._eat_body():
                break

    def _eat_preamble(self):
        buf = self._buf
        if self._at_start:
            if buf.startswith(self._opening):
                n = len(self._opening)
                if len(buf) < n + 2:
                    return False
                # 流起点的分隔行,尾巴对不上就是结构坏了
                self._delim_tail(buf[n:n + 2])
                self._buf = b"" if self._state is _DONE else buf[n + 2:]
                return True
            if self._opening.startswith(buf):
                # 还分不清是不是起始分隔行,等字节到齐
                return False
            self._at_start = False
        pos = 0
        while True:
            i = buf.find(self._marker, pos)
            if i < 0:
                # 前导内容没用,只留可能是分隔行开头的一小截
                k = self._tail_len(buf)
                self._buf = buf[len(buf) - k:] if k else b""
                return False
            if i + len(self._marker) + 2 > len(buf):
                # 候选分隔行的尾巴没到齐,等下一块
                self._buf = buf[i:]
                return False
            tail = buf[i + len(self._marker):i + len(self._marker) + 2]
            if tail in (b"--", b"\r\n"):
                self._delim_tail(tail)
                self._buf = (b"" if self._state is _DONE
                             else buf[i + len(self._marker) + 2:])
                return True
            pos = i + 1  # 长得像而已,继续找

    def _eat_headers(self):
        i = self._buf.find(b"\r\n\r\n")
        if i < 0:
            # 头部可能被切开了,先攒着
            return False
        block = self._buf[:i]
        self._buf = self._buf[i + 4:]
        headers = parse_header_block(block)
        params = parse_params(headers.get("content-disposition", ""))
        self._sink.begin_part(headers, params)
        self._open = True
        self._state = _BODY
        return True

    def _eat_body(self):
        buf = self._buf
        pos = 0
        while True:
            i = buf.find(self._marker, pos)
            if i < 0:
                # 块尾这一截可能是分隔行开头,先留在手里
                k = self._tail_len(buf)
                self._write(buf[:-k] if k else buf)
                self._buf = buf[len(buf) - k:] if k else b""
                return False
            if i + len(self._marker) + 2 > len(buf):
                # 候选分隔行的尾巴没到齐,等下一块再判
                self._write(buf[:i])
                self._buf = buf[i:]
                return False
            tail = buf[i + len(self._marker):i + len(self._marker) + 2]
            if tail in (b"--", b"\r\n"):
                self._write(buf[:i])
                self._end_part()
                self._delim_tail(tail)
                self._buf = (b"" if self._state is _DONE
                             else buf[i + len(self._marker) + 2:])
                return True
            pos = i + 1  # 正文里长得像的字节,继续找

    def _delim_tail(self, tail):
        """分隔行本体之后:-- 是收尾,CRLF 表示后面还跟着一个部分。"""
        if tail == b"--":
            self._state = _DONE
            return
        if tail == b"\r\n":
            self._state = _HEADERS
            return
        raise ParseError("malformed boundary line")

    def _write(self, data):
        if data:
            self._sink.write(data)

    def _end_part(self):
        if self._open:
            self._sink.end_part()
            self._open = False

    def _tail_len(self, data):
        """data 末尾是分隔行开头的一截就返回它的长度,否则返回 0。"""
        limit = min(len(data), len(self._marker) - 1)
        for k in range(limit, 0, -1):
            if self._marker.startswith(data[-k:]):
                return k
        return 0
