"""朴素全量解析:整份 body 拿在手里,一次切完。

语义基准,写得直白,不管内存;头部块借 headers.py 拆,参数这块
自己再走一遍,算得慢但算得准。MultipartParser 是增量实现,切出来
的东西要和这里一致。
"""

from .errors import ParseError
from .headers import parse_header_block
from .sink import Part


def parse_all(body, boundary):
    """把整份 body 解析成 Part 列表;结构不完整就抛 ParseError。"""
    if isinstance(boundary, str):
        boundary = boundary.encode("ascii")
    if not boundary:
        raise ValueError("boundary must not be empty")
    opening = b"--" + boundary
    marker = b"\r\n--" + boundary
    if body.startswith(opening):
        pos = len(opening)
    else:
        i = _find_marker(body, 0, marker)
        if i < 0:
            raise ParseError("no boundary line in body")
        pos = i + len(marker)
    parts = []
    while True:
        head = body[pos:pos + 2]
        if head == b"--":
            return parts
        if head != b"\r\n":
            raise ParseError("malformed boundary line")
        pos += 2
        end = body.find(b"\r\n\r\n", pos)
        if end < 0:
            raise ParseError("unterminated part headers")
        headers = parse_header_block(body[pos:end])
        params = _params_of(headers.get("content-disposition", ""))
        pos = end + 4
        nxt = _find_marker(body, pos, marker)
        if nxt < 0:
            raise ParseError("missing closing boundary")
        parts.append(Part(headers, params, body[pos:nxt]))
        pos = nxt + len(marker)


def _params_of(value):
    """Content-Disposition 值里的分号参数,引号值里的反斜杠转义还原。"""
    params = {}
    pos = 0
    while True:
        semi = value.find(";", pos)
        if semi < 0:
            return params
        pos = semi + 1
        while pos < len(value) and value[pos] == " ":
            pos += 1
        eq = value.find("=", pos)
        if eq < 0:
            return params
        name = value[pos:eq].strip().lower()
        pos = eq + 1
        while pos < len(value) and value[pos] == " ":
            pos += 1
        if pos < len(value) and value[pos] == '"':
            pos += 1
            part = []
            while pos < len(value):
                ch = value[pos]
                if ch == "\\" and pos + 1 < len(value):
                    part.append(value[pos + 1])
                    pos += 2
                    continue
                if ch == '"':
                    pos += 1
                    break
                part.append(ch)
                pos += 1
            if name:
                params[name] = "".join(part)
        else:
            end = value.find(";", pos)
            if end < 0:
                end = len(value)
            if name:
                params[name] = value[pos:end].strip()
            pos = end


def _find_marker(body, pos, marker):
    """从 pos 起找真正的分隔行。

    分隔行后面必须跟 CRLF、--,或者流正好在那里结束;跟别的字符
    的只是正文里长得像的字节,不算分隔行。
    """
    while True:
        i = body.find(marker, pos)
        if i < 0:
            return -1
        tail = body[i + len(marker):i + len(marker) + 2]
        if tail in (b"", b"--", b"\r\n"):
            return i
        pos = i + 1
