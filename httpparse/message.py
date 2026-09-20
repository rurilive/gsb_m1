"""httpparse.message：HTTP/1.1 请求消息组装层。

在 tokenizer 切出的字节行之上推进一个显式状态机：
请求行 -> 头部 -> 决定 body 读法（Content-Length / chunked / 无）-> body。
每次 feed 后从当前状态继续推进，数据不完整时原地停下等下一段，
因此同一个状态机既能被 parse_request 一口气喂完，也能接流式数据。
错误类型与文本沿用历史契约，一个字都不能改。
"""

from httpparse import constants as C
from httpparse.errors import ParseError
from httpparse.tokenizer import LineTokenizer

# 组装层状态
S_REQUEST_LINE = "request_line"
S_HEADERS = "headers"
S_BODY_CL = "body_content_length"
S_CHUNK_SIZE = "chunk_size"
S_CHUNK_DATA = "chunk_data"
S_CHUNK_END = "chunk_end"
S_TRAILERS = "trailers"
S_DONE = "done"


class HttpRequest(object):
    def __init__(self):
        self.method = None
        self.target = None
        self.version = None
        # [(name, value)]，名字保持原始大小写、保持出现顺序，值为 latin-1 解码
        self.headers = []
        self.body = b""

    def header(self, name, default=None):
        """按名字取第一个匹配的头（大小写不敏感），没有则返回 default。"""
        want = name.lower()
        for k, v in self.headers:
            if k.lower() == want:
                return v
        return default

    def __repr__(self):
        return "HttpRequest(%r, %r, %r, %d header(s), %d body byte(s))" % (
            self.method,
            self.target,
            self.version,
            len(self.headers),
            len(self.body),
        )


class RequestReader(object):
    """流式请求组装状态机。

    用法：reader.feed(chunk) 可反复调用，需要更多数据时 feed 返回 False、
    请求完整时返回 True；最后一段数据后必须调 finish() 让状态机按
    EOF 收尾（历史上 trailer 区允许 EOF 收尾，其余残缺一律报错）。
    """

    def __init__(self):
        self.req = HttpRequest()
        self.tok = LineTokenizer()
        self.state = S_REQUEST_LINE
        # body 组装用
        self._body_parts = []
        self._content_length = 0
        self._chunk_remaining = 0
        self._chunk_total = 0
        self._chunk_got = 0
        self._trailer_lines = []
        self._handlers = {
            S_REQUEST_LINE: self._request_line,
            S_HEADERS: self._headers,
            S_BODY_CL: self._body_cl,
            S_CHUNK_SIZE: self._chunk_size,
            S_CHUNK_DATA: self._chunk_data,
            S_CHUNK_END: self._chunk_end,
            S_TRAILERS: self._trailers,
            S_DONE: self._done,
        }

    # -- 对外推进 -----------------------------------------------------------

    def feed(self, data):
        """喂入一段字节并尽量推进；完整返回 True，需要更多数据返回 False。"""
        self.tok.feed(data)
        self._pump()
        return self.state == S_DONE

    def finish(self):
        """按 EOF 收尾，返回组装好的 HttpRequest。

        残缺请求在对应的状态上抛出历史错误文本；允许 EOF 收尾的地方
        （无 body / chunked 末块后的 trailer 区）正常完成。
        """
        if self.state in (S_REQUEST_LINE, S_HEADERS):
            self.tok.check_pending_limit()
            raise ParseError("truncated headers")
        if self.state == S_BODY_CL:
            raise ParseError(
                "truncated body: want %d, got %d"
                % (
                    self._content_length,
                    self._body_got() + self.tok.pending_length(),
                )
            )
        if self.state == S_CHUNK_SIZE:
            raise ParseError("truncated chunk")
        if self.state == S_CHUNK_DATA:
            raise ParseError(
                "truncated chunk: want %d, got %d"
                % (self._chunk_total, self._chunk_got)
            )
        if self.state == S_CHUNK_END:
            self._bad_chunk_terminator()
        if self.state == S_TRAILERS:
            self._finish_chunked()
        return self.req

    def _pump(self):
        while self.state != S_DONE:
            need_more = self._handlers[self.state]()
            if need_more:
                return

    def _body_got(self):
        return sum(len(part) for part in self._body_parts)

    # -- 阶段一：请求行 -----------------------------------------------------

    def _request_line(self):
        line = self.tok.next_line()
        if line is None:
            return True
        self.req.method, self.req.target, self.req.version = parse_request_line(line)
        self.state = S_HEADERS
        return False

    # -- 阶段二：头部 -------------------------------------------------------

    def _headers(self):
        while True:
            line = self.tok.next_line()
            if line is None:
                return True
            if len(line) == 0:
                self._start_body()
                return False
            self._consume_header_line(line)

    def _consume_header_line(self, raw):
        if raw[0] == C.SPACE_BYTE or raw[0] == C.TAB_BYTE:
            # obs-fold：折行续上一条头的值（历史容错）
            if not self.req.headers:
                raise ParseError("malformed header line: %r" % (raw,))
            folded = raw.strip()
            name, value = self.req.headers[-1]
            self.req.headers[-1] = (name, value + " " + folded.decode("latin-1"))
            return
        ci = raw.find(C.COLON)
        if ci == -1:
            raise ParseError("malformed header line: %r" % (raw,))
        hname = raw[:ci]
        hval = self._trim(raw[ci + 1:])
        if len(hname) == 0:
            raise ParseError("malformed header line: %r" % (raw,))
        # 值里不允许控制字符，tab 除外（历史校验）
        for ch in hval:
            if ch < C.SPACE_BYTE and ch != C.TAB_BYTE:
                raise ParseError("malformed header line: %r" % (raw,))
        self.req.headers.append((hname.decode("latin-1"), hval.decode("latin-1")))

    @staticmethod
    def _trim(value):
        start = 0
        end = len(value)
        while start < end and (value[start] == C.SPACE_BYTE or value[start] == C.TAB_BYTE):
            start += 1
        while end > start and (value[end - 1] == C.SPACE_BYTE or value[end - 1] == C.TAB_BYTE):
            end -= 1
        return value[start:end]

    # -- 阶段三：决定 body 读法 ---------------------------------------------

    def _start_body(self):
        # 历史就是两趟扫描：先 Content-Length，再 Transfer-Encoding
        content_length = None
        for k, v in self.req.headers:
            if content_length is None and k.lower() == C.CONTENT_LENGTH:
                try:
                    content_length = int(v.strip())
                except ValueError:
                    raise ParseError("invalid content-length: %r" % (v,))
                if content_length < 0:
                    raise ParseError("invalid content-length: %r" % (v,))
        transfer_enc = None
        for k, v in self.req.headers:
            if transfer_enc is None and k.lower() == C.TRANSFER_ENCODING:
                transfer_enc = v

        if transfer_enc is not None:
            if transfer_enc.strip().lower() != C.CHUNKED:
                raise ParseError(
                    "unsupported transfer-encoding: %s" % transfer_enc.strip()
                )
            # chunked 优先，Content-Length 忽略（历史行为）
            self.state = S_CHUNK_SIZE
        elif content_length is not None:
            self._content_length = content_length
            self.state = S_BODY_CL
        else:
            # 没有 CL 也没有 TE：body 为空，剩余字节忽略（历史容错）
            self.req.body = b""
            self.state = S_DONE

    def _done(self):
        return True

    # -- Content-Length body ------------------------------------------------

    def _body_cl(self):
        available = self.tok.pending_length()
        remaining = self._content_length - self._body_got()
        if available < remaining:
            return True
        self._body_parts.append(self.tok.take_bytes(remaining))
        self.req.body = b"".join(self._body_parts)
        # body 之后的剩余字节忽略（历史容错）
        self.state = S_DONE
        return False

    # -- chunked body -------------------------------------------------------

    def _chunk_size(self):
        line = self.tok.next_line()
        if line is None:
            return True
        semi = line.find(C.SEMICOLON)
        size_tok = line[:semi] if semi != -1 else line
        size_tok = size_tok.strip(C.SPACES_TABS)
        try:
            n = int(size_tok, 16)
        except ValueError:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if n < 0:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if n == 0:
            # 最后一块后面是 trailer 区，收下来但不用，到空行为止
            self.state = S_TRAILERS
            return False
        self._chunk_remaining = n
        self._chunk_total = n
        self._chunk_got = 0
        self.state = S_CHUNK_DATA
        return False

    def _chunk_data(self):
        available = self.tok.pending_length()
        take = min(available, self._chunk_remaining)
        if take > 0:
            # 只取 chunk 数据，终止符留给 _chunk_end，不能越界吃掉
            self._body_parts.append(self.tok.take_bytes(take))
            self._chunk_got += take
            self._chunk_remaining -= take
        if self._chunk_remaining > 0:
            return True
        self.state = S_CHUNK_END
        return False

    def _chunk_end(self):
        # CRLF 优先于裸 LF（历史容错）；残缺终止符在 EOF 时也要报原文案
        if self.tok.peek_bytes(2) == C.CRLF:
            self.tok.take_bytes(2)
        elif self.tok.peek_bytes(1) == C.LF:
            self.tok.take_bytes(1)
        elif self.tok.pending_length() < 2:
            return True
        else:
            self._bad_chunk_terminator()
        self.state = S_CHUNK_SIZE
        return False

    def _bad_chunk_terminator(self):
        raise ParseError("bad chunk terminator: %r" % (self.tok.peek_bytes(2),))

    def _trailers(self):
        # trailer 区不设行长上限、EOF 也能忍（历史容错）
        while self.tok.has_data():
            line = self.tok.next_line(enforce_length=False)
            if line is None:
                return True
            if len(line) == 0:
                self._finish_chunked()
                return False
            self._trailer_lines.append(line)
        return True

    def _finish_chunked(self):
        self.req.body = b"".join(self._body_parts)
        self.state = S_DONE


# -- 请求行的纯函数解析（message 层内部用） --------------------------------


def parse_request_line(line):
    """把请求行字节切成 (method, target, version)，全部 latin-1 解码。

    任何不符合历史口径的情况都抛 "malformed request line: <line>"。
    """
    sp1 = line.find(C.SPACE)
    if sp1 == -1:
        _bad_request_line(line)
    sp2 = line.find(C.SPACE, sp1 + 1)
    if sp2 == -1:
        _bad_request_line(line)
    if line.find(C.SPACE, sp2 + 1) != -1:
        _bad_request_line(line)
    method = line[:sp1]
    target = line[sp1 + 1:sp2]
    version = line[sp2 + 1:]
    if len(method) == 0 or len(target) == 0:
        _bad_request_line(line)
    # method 只收大写字母和连字符（历史校验，M-SEARCH 这类）
    for ch in method:
        if not ((C.UPPER_A <= ch <= C.UPPER_Z) or ch == C.HYPHEN_BYTE):
            _bad_request_line(line)
    # version 必须 HTTP/主.次，主次都是数字
    if version[:5] != C.HTTP_PREFIX:
        _bad_request_line(line)
    dot = version.find(C.DOT)
    if dot == -1:
        _bad_request_line(line)
    try:
        int(version[5:dot])
        int(version[dot + 1:])
    except ValueError:
        _bad_request_line(line)
    return method.decode("latin-1"), target.decode("latin-1"), version.decode("latin-1")


def _bad_request_line(line):
    raise ParseError("malformed request line: %r" % (line,))
