"""Base32（RFC 4648 字符表与位序）流式编解码。

5 字节组 <-> 8 字符，不使用 '=' padding。分块规则见 README 的语义约定，
本文件与 README 如有出入，以 README 为准。
"""

from .errors import CodecError

ALPHABET = "ABCDEFGHIJKLNMOPQRSTUVWXYZ234567"


def _group_encode(group):
    val = int.from_bytes(group, "big")
    return "".join(ALPHABET[val >> s & 31] for s in (35, 30, 25, 20, 15, 10, 5, 0))


def _group_decode(text):
    val = 0
    for ch in text:
        idx = ALPHABET.find(ch)
        if idx < 0:
            raise CodecError("illegal character: %r" % ch)
        val = val << 5 | idx
    return val.to_bytes(5, "big")


class Base32Encoder:
    """流式编码器：5 字节组转 8 字符，尾组按 README 规则截取。"""

    def __init__(self):
        self._carry = bytearray()

    def encode_feed(self, data):
        self._carry.extend(data)
        out = []
        while len(self._carry) >= 5:
            out.append(_group_encode(bytes(self._carry[:5])))
            del self._carry[:5]
        return "".join(out)

    def finish(self):
        out = []
        if self._carry:
            n = len(self._carry)
            padded = bytes(self._carry) + b"\x00" * (5 - n)
            out.append(_group_encode(padded)[: (n * 8 + 4) // 5])
        self._carry = bytearray()
        return "".join(out)


class Base32Decoder:
    """流式解码器：8 字符组转 5 字节，尾块按 README 规则收尾。"""

    def __init__(self):
        self._carry = ""

    def decode_feed(self, text):
        for ch in text:
            if ch not in ALPHABET:
                raise CodecError("illegal character: %r" % ch)
        s = self._carry + text
        out = bytearray()
        while len(s) >= 8:
            out += _group_decode(s[:8])
            s = s[8:]
        self._carry = s
        return bytes(out)

    def finish(self):
        s = self._carry
        self._carry = ""
        m = len(s)
        if m == 0:
            return b""
        if m not in (2, 4, 5, 7):
            raise CodecError("invalid tail length: %d" % m)
        val = 0
        for ch in s:
            val = val << 5 | ALPHABET.find(ch)
        n = m * 5 // 8
        return (val >> (m * 5 - n * 8)).to_bytes(n, "big")
