"""httpparse.parser：HTTP/1.1 请求解析（请求头 + Content-Length / chunked body）。

2018 年给内部网关写的，一口气把整个请求吃完再返回。行为被 tests/ 锁定，
错误文本是契约的一部分（下游日志采集在正则匹配），别改。
"""


class ParseError(ValueError):
    """请求不合法。"""


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


def parse_request(data):
    """解析一个完整的 HTTP/1.1 请求（头部必选，body 按 CL/chunked 跟随）。

    行结束符 \\r\\n 和裸 \\n 都认（历史容错）。头块以第一个空行结束。
    没有 CL 也没有 chunked 时 body 为空，头部之后的剩余字节忽略（历史容错）。
    Transfer-Encoding: chunked 优先于 Content-Length（历史行为）。
    行长度上限按含换行符的整行字节数算，8192（历史口径）。
    """
    if isinstance(data, str):
        raise TypeError("parse_request expects bytes")
    if len(data) == 0:
        raise ParseError("empty request")

    req = HttpRequest()
    pos = 0

    # ---------- 第一段：请求行 ----------
    nl = data.find(b"\n")
    if nl == -1:
        if len(data) - pos > 8192:
            raise ParseError("line too long: %d bytes" % (len(data) - pos))
        raise ParseError("truncated headers")
    if nl - pos > 8192:
        raise ParseError("line too long: %d bytes" % (nl - pos))
    line = data[pos:nl]
    pos = nl + 1
    if len(line) > 0 and line[len(line) - 1] == 13:
        line = line[0:len(line) - 1]
    # 手工扫描两个空格把请求行切成三段
    sp1 = line.find(b" ")
    if sp1 == -1:
        raise ParseError("malformed request line: %r" % (line,))
    sp2 = line.find(b" ", sp1 + 1)
    if sp2 == -1:
        raise ParseError("malformed request line: %r" % (line,))
    if line.find(b" ", sp2 + 1) != -1:
        raise ParseError("malformed request line: %r" % (line,))
    m = line[0:sp1]
    t = line[sp1 + 1:sp2]
    v = line[sp2 + 1:len(line)]
    if len(m) == 0 or len(t) == 0:
        raise ParseError("malformed request line: %r" % (line,))
    # method 只收大写字母和连字符（历史校验，M-SEARCH 这类）
    m_ok = True
    for i in range(len(m)):
        c = m[i:i + 1]
        if not ((c >= b"A" and c <= b"Z") or c == b"-"):
            m_ok = False
            break
    if not m_ok:
        raise ParseError("malformed request line: %r" % (line,))
    # version 必须 HTTP/主.次，主次都是数字
    if v[0:5] != b"HTTP/":
        raise ParseError("malformed request line: %r" % (line,))
    dot = v.find(b".")
    if dot == -1:
        raise ParseError("malformed request line: %r" % (line,))
    try:
        int(v[5:dot])
        int(v[dot + 1:len(v)])
    except ValueError:
        raise ParseError("malformed request line: %r" % (line,))
    req.method = m.decode("latin-1")
    req.target = t.decode("latin-1")
    req.version = v.decode("latin-1")

    # ---------- 第二段：头部 ----------
    prev_key = None
    while True:
        if pos >= len(data):
            raise ParseError("truncated headers")
        nl = data.find(b"\n", pos)
        if nl == -1:
            if len(data) - pos > 8192:
                raise ParseError("line too long: %d bytes" % (len(data) - pos))
            raise ParseError("truncated headers")
        if nl - pos > 8192:
            raise ParseError("line too long: %d bytes" % (nl - pos))
        raw = data[pos:nl]
        pos = nl + 1
        if len(raw) > 0 and raw[len(raw) - 1] == 13:
            raw = raw[0:len(raw) - 1]
        if len(raw) == 0:
            # 空行，头块结束
            break
        if raw[0] == 32 or raw[0] == 9:
            # obs-fold：折行续上一条头的值（历史容错）
            if prev_key is None:
                raise ParseError("malformed header line: %r" % (raw,))
            folded = raw.strip()
            old = req.headers[len(req.headers) - 1]
            req.headers[len(req.headers) - 1] = (
                old[0],
                old[1] + " " + folded.decode("latin-1"),
            )
            continue
        ci = raw.find(b":")
        if ci == -1:
            raise ParseError("malformed header line: %r" % (raw,))
        hname = raw[0:ci]
        hval = raw[ci + 1:len(raw)]
        # 手工去掉值两端的空白（32 空格 / 9 tab）
        vs = 0
        while vs < len(hval) and (hval[vs] == 32 or hval[vs] == 9):
            vs = vs + 1
        ve = len(hval)
        while ve > vs and (hval[ve - 1] == 32 or hval[ve - 1] == 9):
            ve = ve - 1
        hval = hval[vs:ve]
        if len(hname) == 0:
            raise ParseError("malformed header line: %r" % (raw,))
        # 值里不允许控制字符，tab（9）除外（历史校验）
        hval_ok = True
        for i in range(len(hval)):
            if hval[i] < 32 and hval[i] != 9:
                hval_ok = False
                break
        if not hval_ok:
            raise ParseError("malformed header line: %r" % (raw,))
        hname_s = hname.decode("latin-1")
        hval_s = hval.decode("latin-1")
        req.headers.append((hname_s, hval_s))
        prev_key = hname_s

    # ---------- 第三段：决定 body 怎么读 ----------
    # 先扫一遍找 Content-Length，再扫一遍找 Transfer-Encoding（历史就这两趟）
    content_length = None
    for k, v in req.headers:
        if content_length is None and k.lower() == "content-length":
            try:
                content_length = int(v.strip())
            except ValueError:
                raise ParseError("invalid content-length: %r" % (v,))
            if content_length < 0:
                raise ParseError("invalid content-length: %r" % (v,))
    transfer_enc = None
    for k, v in req.headers:
        if transfer_enc is None and k.lower() == "transfer-encoding":
            transfer_enc = v

    if transfer_enc is not None:
        if transfer_enc.strip().lower() != "chunked":
            raise ParseError(
                "unsupported transfer-encoding: %s" % transfer_enc.strip()
            )
        # chunked 优先，Content-Length 忽略（历史行为）
        buf = bytearray()
        trailers = []
        while True:
            nl = data.find(b"\n", pos)
            if nl == -1:
                raise ParseError("truncated chunk")
            if nl - pos > 8192:
                raise ParseError("line too long: %d bytes" % (nl - pos))
            size_raw = data[pos:nl]
            pos = nl + 1
            if len(size_raw) > 0 and size_raw[len(size_raw) - 1] == 13:
                size_raw = size_raw[0:len(size_raw) - 1]
            semi = size_raw.find(b";")
            if semi != -1:
                size_tok = size_raw[0:semi]
            else:
                size_tok = size_raw
            size_tok = size_tok.strip(b" \t")
            try:
                n = int(size_tok, 16)
            except ValueError:
                raise ParseError("bad chunk size: %r" % (size_tok,))
            if n < 0:
                raise ParseError("bad chunk size: %r" % (size_tok,))
            if n == 0:
                # 最后一块后面是 trailer 区，收下来但不用，到空行为止
                # （EOF 也能忍，历史容错）
                while True:
                    if pos >= len(data):
                        break
                    nl = data.find(b"\n", pos)
                    if nl == -1:
                        break
                    traw = data[pos:nl]
                    pos = nl + 1
                    if len(traw) > 0 and traw[len(traw) - 1] == 13:
                        traw = traw[0:len(traw) - 1]
                    if len(traw) == 0:
                        break
                    trailers.append(traw)
                break
            if pos + n > len(data):
                raise ParseError(
                    "truncated chunk: want %d, got %d" % (n, len(data) - pos)
                )
            end = pos + n
            buf = buf + data[pos:end]
            pos = end
            if data[pos:pos + 2] == b"\r\n":
                pos = pos + 2
            elif data[pos:pos + 1] == b"\n":
                pos = pos + 1
            else:
                raise ParseError("bad chunk terminator: %r" % (data[pos:pos + 2],))
        req.body = bytes(buf)
        return req

    if content_length is not None:
        if pos + content_length > len(data):
            raise ParseError(
                "truncated body: want %d, got %d"
                % (content_length, len(data) - pos)
            )
        end = pos + content_length
        req.body = data[pos:end]
        # body 之后的剩余字节忽略（历史容错）
        return req

    # 没有 CL 也没有 TE：body 为空，剩余字节忽略（历史容错）
    req.body = b""
    return req
