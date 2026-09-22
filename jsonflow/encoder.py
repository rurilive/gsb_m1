"""把 Python 对象写回 JSON 文本。

输出口径跟标准库 json 的默认值一致：", " 跟 ": " 两个分隔符，非 ASCII 一律转义。
"""

from .numbers import Num

_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def encode_string(value):
    """给字符串加引号并转义。"""
    out = ['"']
    for ch in value:
        escaped = _ESCAPES.get(ch)
        if escaped is not None:
            out.append(escaped)
            continue
        code = ord(ch)
        if code < 0x20 or code > 0x7E:
            if code > 0xFFFF:
                code -= 0x10000
                out.append("\\u%04x\\u%04x" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
            else:
                out.append("\\u%04x" % code)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


class Encoder:
    """默认序列化器。"""

    def __init__(self):
        self.chunks = []
        self._number_text = {}

    def encode(self, value):
        chunks = self.chunks
        if value is None or value is True or value is False:
            chunks.append("null" if value is None else ("true" if value else "false"))
            return
        if isinstance(value, str):
            chunks.append(encode_string(value))
            return
        if isinstance(value, Num):
            chunks.append(value.text)
            return
        if isinstance(value, int):
            chunks.append(str(value))
            return
        if isinstance(value, float):
            chunks.append(self._float_text(value))
            return
        if isinstance(value, (list, tuple)):
            chunks.append("[")
            for index, item in enumerate(value):
                if index:
                    chunks.append(", ")
                self.encode(item)
            chunks.append("]")
            return
        if isinstance(value, dict):
            chunks.append("{")
            for index, (key, item) in enumerate(value.items()):
                if index:
                    chunks.append(", ")
                if not isinstance(key, str):
                    raise TypeError("对象的键必须是字符串，收到 %r" % (type(key).__name__,))
                chunks.append(encode_string(key))
                chunks.append(": ")
                self.encode(item)
            chunks.append("}")
            return
        raise TypeError("不能序列化的类型 %r" % (type(value).__name__,))

    def _float_text(self, value):
        text = self._number_text.get(value)
        if text is None:
            text = repr(value)
            self._number_text[value] = text
        return text


def dumps(obj):
    """把对象序列化成 JSON 文本。"""
    encoder = Encoder()
    encoder.encode(obj)
    return "".join(encoder.chunks)
