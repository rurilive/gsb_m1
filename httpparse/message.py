"""httpparse.message：HTTP 报文组装层（第二层）。

tokenizer 只给出行/字节，本层负责把它们推进成一个 HttpRequest：
请求行 -> 头部（含 obs-fold）-> 按 Content-Length / chunked 读 body。
推进由显式状态机驱动：每来一段数据就按当前状态消费能确定的部分，
缺行/缺字节就停在原地等下一段，因此一次喂完和一段段喂等价。
"""

from .constants import (
    CHUNKED,
    CHUNK_EXT_SEP,
    CHUNK_SIZE_STRIP,
    COLON,
    CONTENT_LENGTH_HEADER,
    CRLF,
    DASH,
    DOT,
    HEX,
    HTTP_PREFIX,
    LATIN1,
    LF,
    MAX_LINE_LENGTH,
    SPACE,
    TAB,
    TRANSFER_ENCODING_HEADER,
    UPPER_A,
    UPPER_Z,
)
from .tokenizer import LineTokenizer, ParseError

__all__ = ["HttpRequest", "ParseError", "RequestAssembler"]


# 状态机的状态
_S_REQUEST_LINE = "request_line"
_S_HEADERS = "headers"
_S_CL_BODY = "cl_body"
_S_CHUNK_SIZE = "chunk_size"
_S_CHUNK_DATA = "chunk_data"
_S_CHUNK_END = "chunk_end"
_S_TRAILERS = "trailers"
_S_DONE = "done"


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


def _strip_ows(raw):
    """去掉值两端的空格/制表（32/9），与历史手工扫描等价。"""
    start = 0
    while start < len(raw) and (raw[start] == SPACE or raw[start] == TAB):
        start += 1
    end = len(raw)
    while end > start and (raw[end - 1] == SPACE or raw[end - 1] == TAB):
        end -= 1
    return raw[start:end]


class RequestAssembler(object):
    """增量组装一个 HTTP/1.1 请求。

    用法：feed(data) 可调用任意多次（流式），数据齐了之后 finish()
    返回 HttpRequest。一口气喂完时就是 parse_request 的实现。
    """

    def __init__(self):
        self._tok = LineTokenizer()
        self.req = HttpRequest()
        self._state = _S_REQUEST_LINE
        self._prev_key = None
        self._body_buf = bytearray()
        self._content_length = 0
        self._chunk_remaining = 0

    def feed(self, data):
        self._tok.feed(data)
        self._advance()

    def finish(self):
        """声明不会再有数据到达；容忍历史上 EOF 即收尾的情形。"""
        self._finish_at_eof()
        if self._state not in (_S_DONE, _S_TRAILERS):
            # 正常路径在 _finish_at_eof 里已经抛错，这里只是兜底
            raise ParseError("truncated headers")
        self.req.body = bytes(self._body_buf)
        return self.req

    # ---------- 状态推进 ----------

    def _advance(self):
        """消费当前缓冲区里所有能确定的行/字节，缺数据则停住。"""
        while True:
            if self._state == _S_REQUEST_LINE:
                line = self._tok.take_line()
                if line is None:
                    return
                self._consume_request_line(line)
                self._state = _S_HEADERS

            elif self._state == _S_HEADERS:
                line = self._tok.take_line()
                if line is None:
                    return
                if len(line) == 0:
                    self._begin_body()
                else:
                    self._consume_header_line(line)

            elif self._state == _S_CL_BODY:
                self._drain_cl_body()
                if self._state != _S_DONE:
                    return

            elif self._state == _S_CHUNK_SIZE:
                line = self._tok.take_line()
                if line is None:
                    return
                self._consume_chunk_size(line)

            elif self._state == _S_CHUNK_DATA:
                self._drain_chunk_data()
                if self._state != _S_CHUNK_END:
                    return

            elif self._state == _S_CHUNK_END:
                if not self._consume_chunk_terminator():
                    return

            elif self._state == _S_TRAILERS:
                # trailer 行不做行长限制（历史口径）
                line = self._tok.take_line(enforce_limit=False)
                if line is None:
                    return
                if len(line) == 0:
                    self._state = _S_DONE
                # 非空 trailer：收下但不进 headers（历史行为：不收不用）

            elif self._state == _S_DONE:
                # 历史容错：body 之后的剩余字节一律忽略
                self._tok.take_rest()
                return

    def _finish_at_eof(self):
        """EOF 时按当前状态补历史容错或报错。"""
        if self._state == _S_REQUEST_LINE:
            pending = self._tok.pending_length()
            if pending == 0:
                raise ParseError("empty request")
            if pending > MAX_LINE_LENGTH:
                raise ParseError("line too long: %d bytes" % pending)
            raise ParseError("truncated headers")

        if self._state == _S_HEADERS:
            if self._tok.pending_length() > MAX_LINE_LENGTH:
                raise ParseError(
                    "line too long: %d bytes" % self._tok.pending_length()
                )
            raise ParseError("truncated headers")

        if self._state == _S_CHUNK_SIZE:
            raise ParseError("truncated chunk")

        if self._state == _S_CHUNK_DATA:
            # got = 本块已经收到的数据字节数（与历史一次性扫描的口径一致）
            raise ParseError(
                "truncated chunk: want %d, got %d"
                % (self._chunk_remaining, self._drained_in_chunk())
            )

        if self._state == _S_CHUNK_END:
            raise ParseError(
                "bad chunk terminator: %r" % self._tok.peek_bytes(2)
            )

        if self._state == _S_CL_BODY:
            # got = 跨所有 feed 已消费进 body 的字节数
            raise ParseError(
                "truncated body: want %d, got %d"
                % (self._content_length, self._cl_received)
            )

        # _S_TRAILERS / _S_DONE：EOF 可直接收尾
        self._tok.take_rest()
        self._state = _S_DONE

    # ---------- 请求行 ----------

    def _consume_request_line(self, line):
        sp1 = line.find(b" ")
        if sp1 == -1:
            raise ParseError("malformed request line: %r" % (line,))
        sp2 = line.find(b" ", sp1 + 1)
        if sp2 == -1:
            raise ParseError("malformed request line: %r" % (line,))
        if line.find(b" ", sp2 + 1) != -1:
            raise ParseError("malformed request line: %r" % (line,))
        method = line[0:sp1]
        target = line[sp1 + 1:sp2]
        version = line[sp2 + 1:len(line)]
        if len(method) == 0 or len(target) == 0:
            raise ParseError("malformed request line: %r" % (line,))
        # method 只收大写字母和连字符（历史校验，M-SEARCH 这类）
        for i in range(len(method)):
            ch = method[i:i + 1]
            if not ((UPPER_A <= ch <= UPPER_Z) or ch == DASH):
                raise ParseError("malformed request line: %r" % (line,))
        # version 必须 HTTP/主.次，主次都是数字
        if version[0:5] != HTTP_PREFIX:
            raise ParseError("malformed request line: %r" % (line,))
        dot = version.find(DOT)
        if dot == -1:
            raise ParseError("malformed request line: %r" % (line,))
        try:
            int(version[5:dot])
            int(version[dot + 1:len(version)])
        except ValueError:
            raise ParseError("malformed request line: %r" % (line,))
        self.req.method = method.decode(LATIN1)
        self.req.target = target.decode(LATIN1)
        self.req.version = version.decode(LATIN1)

    # ---------- 头部 ----------

    def _consume_header_line(self, raw):
        # obs-fold：折行续上一条头的值（历史容错）
        if raw[0] == SPACE or raw[0] == TAB:
            if self._prev_key is None:
                raise ParseError("malformed header line: %r" % (raw,))
            folded = raw.strip()
            name, value = self.req.headers[-1]
            self.req.headers[-1] = (
                name,
                value + " " + folded.decode(LATIN1),
            )
            return
        ci = raw.find(COLON)
        if ci == -1:
            raise ParseError("malformed header line: %r" % (raw,))
        name = raw[0:ci]
        value = _strip_ows(raw[ci + 1:len(raw)])
        if len(name) == 0:
            raise ParseError("malformed header line: %r" % (raw,))
        # 值里不允许控制字符，tab（9）除外（历史校验）
        for ch in value:
            if ch < SPACE and ch != TAB:
                raise ParseError("malformed header line: %r" % (raw,))
        self.req.headers.append((name.decode(LATIN1), value.decode(LATIN1)))
        self._prev_key = name.decode(LATIN1)

    # ---------- 决定 body 读法 ----------

    def _begin_body(self):
        # 先扫 Content-Length 再扫 Transfer-Encoding（历史就这两趟）
        content_length = None
        for name, value in self.req.headers:
            if content_length is None and name.lower() == CONTENT_LENGTH_HEADER:
                try:
                    content_length = int(value.strip())
                except ValueError:
                    raise ParseError("invalid content-length: %r" % (value,))
                if content_length < 0:
                    raise ParseError("invalid content-length: %r" % (value,))
        transfer_enc = None
        for name, value in self.req.headers:
            if transfer_enc is None and name.lower() == TRANSFER_ENCODING_HEADER:
                transfer_enc = value

        if transfer_enc is not None:
            if transfer_enc.strip().lower() != CHUNKED:
                raise ParseError(
                    "unsupported transfer-encoding: %s" % transfer_enc.strip()
                )
            # chunked 优先，Content-Length 忽略（历史行为）
            self._state = _S_CHUNK_SIZE
            self._advance()
            return

        if content_length is not None:
            self._content_length = content_length
            # 跨 feed 已消费进 body 的字节数，EOF 报 want/got 时用
            self._cl_received = 0
            self._state = _S_CL_BODY
            self._advance()
            return

        # 没有 CL 也没有 TE：body 为空，剩余字节忽略（历史容错）
        self._state = _S_DONE
        self._advance()

    # ---------- Content-Length body ----------

    def _drain_cl_body(self):
        available = self._tok.pending_length()
        wanted = self._content_length - len(self._body_buf)
        take = wanted if wanted <= available else available
        if take > 0:
            self._body_buf.extend(self._tok.take_bytes(take))
            self._cl_received += take
        if self._cl_received >= self._content_length:
            # body 之后的剩余字节忽略（历史容错）
            self._state = _S_DONE

    # ---------- chunked body ----------

    def _consume_chunk_size(self, line):
        semi = line.find(CHUNK_EXT_SEP)
        if semi != -1:
            size_tok = line[0:semi]
        else:
            size_tok = line
        size_tok = size_tok.strip(CHUNK_SIZE_STRIP)
        try:
            n = int(size_tok, HEX)
        except ValueError:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if n < 0:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if n == 0:
            # 最后一块后面是 trailer 区，收下来但不用，到空行为止
            # （EOF 也能忍，历史容错）
            self._state = _S_TRAILERS
            self._advance()
            return
        self._chunk_remaining = n
        self._chunk_start = len(self._body_buf)
        self._state = _S_CHUNK_DATA
        self._advance()

    def _drained_in_chunk(self):
        return len(self._body_buf) - self._chunk_start

    def _drain_chunk_data(self):
        # 只拿本块还缺的字节，绝不能把后面的终止符吞进来
        need = self._chunk_remaining - self._drained_in_chunk()
        available = self._tok.pending_length()
        take = need if need <= available else available
        if take > 0:
            self._body_buf.extend(self._tok.take_bytes(take))
        if self._drained_in_chunk() >= self._chunk_remaining:
            self._state = _S_CHUNK_END
            self._advance()

    def _consume_chunk_terminator(self):
        """消费 chunk 数据后的 CRLF/裸 LF；数据不够时返回 False 等待。"""
        if self._tok.peek_bytes(2) == CRLF:
            self._tok.skip_bytes(2)
            self._state = _S_CHUNK_SIZE
            return True
        if self._tok.peek_bytes(1) == LF:
            self._tok.skip_bytes(1)
            self._state = _S_CHUNK_SIZE
            return True
        if self._tok.pending_length() >= 2:
            # 头一个字节不是 CR/LF，或 CR 后面跟的不是 LF
            raise ParseError(
                "bad chunk terminator: %r" % self._tok.peek_bytes(2)
            )
        # 只剩 1 个字节（可能是 CRLF 的前半段）或 0 个：等下一段
        return False
