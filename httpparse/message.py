"""message 组装层：把 tokenizer 切出来的行/字节推进成一个 HttpRequest。

这里持有全部解析状态，状态在显式的 state 上推进：

    REQUEST_LINE -> HEADERS
    HEADERS      -> BODY_LENGTH / CHUNK_SIZE / DONE（看 CL / TE）
    BODY_LENGTH  -> DONE
    CHUNK_SIZE   -> CHUNK_DATA -> CHUNK_END -> CHUNK_SIZE（循环）
                 -> TRAILERS（读到 0 长块）-> DONE

每走一步只从 tokenizer 取"眼下这一步需要的量"，取不到就返回
NEED_DATA，不假设后面的数据已经到齐。parse_request 一口气喂完再
finish()；下个版本做流式时，改为数据到一段 feed 一段、反复 pump()
即可，解析逻辑不用动。
"""

from httpparse.constants import (
    CHUNKED,
    COLON,
    CRLF,
    LF,
    CONTENT_LENGTH,
    DOT,
    HTTP_PREFIX,
    LATIN1,
    MAX_LINE_LENGTH,
    METHOD_A,
    METHOD_DASH,
    METHOD_Z,
    SEMICOLON,
    SPACE,
    TAB,
    TRANSFER_ENCODING,
    WHITESPACE,
)
from httpparse.errors import ParseError

(
    _STATE_REQUEST_LINE,
    _STATE_HEADERS,
    _STATE_BODY_LENGTH,
    _STATE_CHUNK_SIZE,
    _STATE_CHUNK_DATA,
    _STATE_CHUNK_END,
    _STATE_TRAILERS,
    _STATE_DONE,
) = range(8)

_NEED_DATA = "need-data"
_DONE = "done"


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


class MessageReader(object):
    """按状态把 tokenizer 的字节流组装成 HttpRequest。"""

    def __init__(self, tokenizer):
        self._tok = tokenizer
        self.request = HttpRequest()
        self._state = _STATE_REQUEST_LINE
        self._prev_key = None
        self._content_length = None
        self._chunk_remaining = 0
        self._chunk_body = bytearray()

    def pump(self):
        """推进状态机；一步数据不够时返回 NEED_DATA，组装完成返回 DONE。"""
        while self._state != _STATE_DONE:
            handler = self._HANDLERS[self._state]
            if handler(self) is _NEED_DATA:
                return _NEED_DATA
        return _DONE

    def finish(self):
        """一口气模式：数据已全部喂完，推不动时按状态报对应的 EOF 错误。"""
        while True:
            # 与 pump() 相同的推进，但最后一次推进视为 EOF：某些状态
            # （如 chunk 终止符只看到一个 CR）流式中途会等下一段，EOF 时
            # 必须按历史口径立刻定性，不能再等。
            if self._state == _STATE_CHUNK_END:
                self._read_chunk_end(at_eof=True)
            if self.pump() is _DONE:
                return self.request
            raise self._eof_error()

    # ---------- 请求行 ----------
    def _read_request_line(self):
        line = self._tok.next_line()
        if line is None:
            return _NEED_DATA
        sp1 = line.find(b" ")
        if sp1 == -1:
            self._bad_request_line(line)
        sp2 = line.find(b" ", sp1 + 1)
        if sp2 == -1:
            self._bad_request_line(line)
        if line.find(b" ", sp2 + 1) != -1:
            self._bad_request_line(line)
        method = line[0:sp1]
        target = line[sp1 + 1:sp2]
        version = line[sp2 + 1:len(line)]
        if len(method) == 0 or len(target) == 0:
            self._bad_request_line(line)
        # method 只收大写字母和连字符（历史校验，M-SEARCH 这类）
        for ch in method:
            if not (METHOD_A <= ch <= METHOD_Z or ch == METHOD_DASH):
                self._bad_request_line(line)
        # version 必须 HTTP/主.次，主次都是数字
        if version[0:5] != HTTP_PREFIX:
            self._bad_request_line(line)
        dot = version.find(DOT)
        if dot == -1:
            self._bad_request_line(line)
        try:
            int(version[5:dot])
            int(version[dot + 1:len(version)])
        except ValueError:
            self._bad_request_line(line)
        self.request.method = method.decode(LATIN1)
        self.request.target = target.decode(LATIN1)
        self.request.version = version.decode(LATIN1)
        self._state = _STATE_HEADERS
        return True

    @staticmethod
    def _bad_request_line(line):
        raise ParseError("malformed request line: %r" % (line,))

    # ---------- 头部 ----------
    def _read_headers(self):
        raw = self._tok.next_line()
        if raw is None:
            return _NEED_DATA
        if len(raw) == 0:
            # 空行，头块结束，决定 body 怎么读
            self._select_body_mode()
            return True
        if raw[0] == SPACE or raw[0] == TAB:
            # obs-fold：折行续上一条头的值（历史容错）
            if self._prev_key is None:
                raise ParseError("malformed header line: %r" % (raw,))
            folded = raw.strip()
            old = self.request.headers[-1]
            self.request.headers[-1] = (
                old[0],
                old[1] + " " + folded.decode(LATIN1),
            )
            return True
        ci = raw.find(COLON)
        if ci == -1:
            raise ParseError("malformed header line: %r" % (raw,))
        hname = raw[0:ci]
        hval = raw[ci + 1:len(raw)]
        # 手工去掉值两端的空白（32 空格 / 9 tab）
        vs = 0
        while vs < len(hval) and (hval[vs] == SPACE or hval[vs] == TAB):
            vs += 1
        ve = len(hval)
        while ve > vs and (hval[ve - 1] == SPACE or hval[ve - 1] == TAB):
            ve -= 1
        hval = hval[vs:ve]
        if len(hname) == 0:
            raise ParseError("malformed header line: %r" % (raw,))
        # 值里不允许控制字符，tab（9）除外（历史校验）
        for ch in hval:
            if ch < SPACE and ch != TAB:
                raise ParseError("malformed header line: %r" % (raw,))
        hname_s = hname.decode(LATIN1)
        self.request.headers.append((hname_s, hval.decode(LATIN1)))
        self._prev_key = hname_s
        return True

    def _select_body_mode(self):
        # 先扫一遍找 Content-Length，再扫一遍找 Transfer-Encoding（历史两趟）
        for k, v in self.request.headers:
            if self._content_length is None and k.lower() == CONTENT_LENGTH:
                try:
                    length = int(v.strip())
                except ValueError:
                    raise ParseError("invalid content-length: %r" % (v,))
                if length < 0:
                    raise ParseError("invalid content-length: %r" % (v,))
                self._content_length = length
        transfer_enc = None
        for k, v in self.request.headers:
            if transfer_enc is None and k.lower() == TRANSFER_ENCODING:
                transfer_enc = v

        if transfer_enc is not None:
            if transfer_enc.strip().lower() != CHUNKED:
                raise ParseError(
                    "unsupported transfer-encoding: %s" % transfer_enc.strip()
                )
            # chunked 优先，Content-Length 忽略（历史行为）
            self._state = _STATE_CHUNK_SIZE
        elif self._content_length is not None:
            self._state = _STATE_BODY_LENGTH
        else:
            # 没有 CL 也没有 TE：body 为空，剩余字节忽略（历史容错）
            self.request.body = b""
            self._state = _STATE_DONE

    # ---------- Content-Length body ----------
    def _read_length_body(self):
        chunk = self._tok.take(self._content_length)
        if chunk is None:
            return _NEED_DATA
        self.request.body = chunk
        # body 之后的剩余字节忽略（历史容错）
        self._state = _STATE_DONE
        return True

    # ---------- chunked body ----------
    def _read_chunk_size(self):
        line = self._tok.next_line()
        if line is None:
            return _NEED_DATA
        semi = line.find(SEMICOLON)
        size_tok = line[0:semi] if semi != -1 else line
        size_tok = size_tok.strip(WHITESPACE)
        try:
            size = int(size_tok, 16)
        except ValueError:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if size < 0:
            raise ParseError("bad chunk size: %r" % (size_tok,))
        if size == 0:
            # 最后一块后面是 trailer 区，收到空行为止（EOF 也能忍，历史容错）
            self._state = _STATE_TRAILERS
        else:
            self._chunk_remaining = size
            self._state = _STATE_CHUNK_DATA
        return True

    def _read_chunk_data(self):
        chunk = self._tok.take(self._chunk_remaining)
        if chunk is None:
            return _NEED_DATA
        self._chunk_body.extend(chunk)
        self._state = _STATE_CHUNK_END
        return True

    def _read_chunk_end(self, at_eof=False):
        tok = self._tok
        if tok.buffered_length == 0:
            return _NEED_DATA
        if tok.starts_with(CRLF):
            tok.consume(len(CRLF))
            self._state = _STATE_CHUNK_SIZE
            return True
        if tok.peek(1) == bytes(bytearray([LF])):
            tok.consume(1)
            self._state = _STATE_CHUNK_SIZE
            return True
        # 终止符错误文本取开头两个字节：流式中途不足两字节时先等下一段
        # （CR 要等可能随后到的 LF；X、z 这类也要等第二字节才能定型文案）；
        # 已声明 EOF 则按历史口径立刻用当前缓冲定性报错
        if not at_eof and tok.buffered_length < 2:
            return _NEED_DATA
        raise ParseError("bad chunk terminator: %r" % (tok.peek(2),))

    def _read_trailers(self):
        # trailer 区历史上不限行长，tokenizer 不在这层卡上限
        line = self._tok.next_line(enforce_length=False)
        if line is None:
            # EOF 也能收尾（历史容错）
            self._finish_chunked()
            return True
        if len(line) == 0:
            self._finish_chunked()
        # 非空 trailer 行收下但不进 headers，继续等空行
        return True

    def _finish_chunked(self):
        self.request.body = bytes(self._chunk_body)
        self._state = _STATE_DONE

    # ---------- 一口气模式下的 EOF 错误（文案与历史逐字一致） ----------
    def _eof_error(self):
        state = self._state
        if state in (_STATE_REQUEST_LINE, _STATE_HEADERS):
            pending = self._tok.buffered_length
            if pending > MAX_LINE_LENGTH:
                return ParseError("line too long: %d bytes" % pending)
            return ParseError("truncated headers")
        if state == _STATE_CHUNK_SIZE:
            return ParseError("truncated chunk")
        if state == _STATE_CHUNK_DATA:
            return ParseError(
                "truncated chunk: want %d, got %d"
                % (self._chunk_remaining, self._tok.buffered_length)
            )
        if state == _STATE_CHUNK_END:
            # 一口气模式不再等后续字节：开头是什么就报什么（与历史一致，
            # 例如尾部恰好是 CR 时报 b'X\r'，缓冲区空时报 b''）
            return ParseError(
                "bad chunk terminator: %r" % (self._tok.peek(2),)
            )
        if state == _STATE_BODY_LENGTH:
            return ParseError(
                "truncated body: want %d, got %d"
                % (self._content_length, self._tok.buffered_length)
            )
        # 不会走到这里：_STATE_TRAILERS 数据不足时 pump 不会返回 NEED_DATA，
        # trailer 处理器在 EOF（next_line 返回 None）时直接收尾成 DONE。
        raise AssertionError("unexpected state: %r" % (state,))

    _HANDLERS = {
        _STATE_REQUEST_LINE: _read_request_line,
        _STATE_HEADERS: _read_headers,
        _STATE_BODY_LENGTH: _read_length_body,
        _STATE_CHUNK_SIZE: _read_chunk_size,
        _STATE_CHUNK_DATA: _read_chunk_data,
        _STATE_CHUNK_END: _read_chunk_end,
        _STATE_TRAILERS: _read_trailers,
    }
