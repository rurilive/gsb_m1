"""Base85（RFC 1924 字符表）流式编解码。

4 字节组 <-> 5 字符。流式分块规则见 README 的语义约定，本文件与
README 如有出入，以 README 为准。
"""

from .errors import CodecError

ALPHABET = ("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "abcdefghijklmnopqrstuvwxyz"
            "!#$%&()*+-;<=>?@^_`{|}~")

_POW85 = (85 ** 4, 85 ** 3, 85 ** 2, 85, 1)
_WS = " \t\r\n\v\f"


def _group_encode(group):
    val = int.from_bytes(group, "big")
    return "".join(ALPHABET[val // p % 85] for p in _POW85)


def _group_decode(text):
    val = 0
    for ch in text:
        idx = ALPHABET.find(ch)
        if idx < 0:
            raise CodecError("illegal character: %r" % ch)
        val = val * 85 + idx
    if val > 0xFFFFFFFF:
        raise CodecError("group value overflows 32 bits")
    return val.to_bytes(4, "big")


class Base85Encoder:
    """流式编码器：encode_feed 可按任意边界分块，finish 收尾。"""

    def __init__(self):
        self._carry = bytearray()

    def encode_feed(self, data):
        buf = bytes(self._carry) + bytes(data)
        out = []
        while len(buf) >= 4:
            out.append(_group_encode(buf[:4]))
            buf = buf[4:]
        self._carry += buf
        return "".join(out)

    def finish(self):
        out = []
        if self._carry:
            n = len(self._carry)
            padded = bytes(self._carry) + b"\x00" * (4 - n)
            out.append(_group_encode(padded)[: (n + 1) % 4])
        self._carry = bytearray()
        return "".join(out)


class Base85Decoder:
    """流式解码器：decode_feed 可按任意边界分块，finish 收尾。"""

    def __init__(self):
        self._carry = ""

    def decode_feed(self, text):
        s = self._carry + text
        s = "".join(ch for ch in s if ch not in _WS)
        for ch in s:
            if ch not in ALPHABET:
                raise CodecError("illegal character: %r" % ch)
        out = bytearray()
        while len(s) >= 5:
            out += _group_decode(s[:5])
            s = s[5:]
        self._carry = s
        return bytes(out)

    def finish(self):
        s = self._carry
        self._carry = ""
        m = len(s)
        if m == 0:
            return b""
        if m == 1:
            raise CodecError("lone trailing character cannot be decoded")
        padded = s + ALPHABET[-1] * (5 - m)
        return _group_decode(padded)[: m - 1]
