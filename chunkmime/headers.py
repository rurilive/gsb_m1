"""头部块与参数的解析。

头部块里每行形如 "Name: value",行间用 CRLF 隔开,块尾的空行
不算在内;Content-Disposition 这类值除了主值还挂着一串分号隔开
的参数,参数值可能用双引号包着。
"""

import re

# 参数名 = 引号值,或参数名 = 裸值(到分号为止)
_PARAM = re.compile(rb"([A-Za-z0-9_.-]+)\s*=\s*(?:\"([^\"]*)\"|([^;]*))")


def parse_header_block(block):
    """把头部块解析成 {小写名字: 值},block 不含结尾的空行。"""
    headers = {}
    for line in block.split(b"\r\n"):
        if not line:
            continue
        i = line.find(b":")
        if i < 0:
            # 没有冒号的行,当噪声跳过
            continue
        name = line[:i].strip().decode("latin-1").lower()
        value = line[i + 1:].lstrip(b" \t").decode("latin-1")
        if name:
            headers[name] = value
    return headers


def parse_params(value):
    """解析 Content-Disposition 值里的参数,返回 {小写名字: 值}。"""
    if not value:
        return {}
    params = {}
    for m in _PARAM.finditer(value.encode("latin-1")):
        name = m.group(1).decode("ascii").lower()
        raw = m.group(2) if m.group(2) is not None else m.group(3)
        params[name] = _decode_value(raw)
    return params


def _decode_value(raw):
    """参数值还原成文本。"""
    return raw.decode("utf-8", "replace").strip()
