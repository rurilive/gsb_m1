"""增量 UTF-8 解码器：按块喂字节、吐文本，供接入网关做流式转码。"""

_BOM = b"\xef\xbb\xbf"


class Utf8DecodeError(ValueError):
    """字节流无法按 UTF-8 解码。"""


def _seq_len(head: int) -> int:
    """按首字节返回该序列应有的字节数；首字节非法时返回 -1。"""
    if head < 0x80:
        return 1
    if head < 0xC0:
        return -1
    if head < 0xE0:
        return 2
    if head < 0xF0:
        return 3
    if head < 0xF8:
        return 4
    return -1


class Utf8Decoder:
    """流式 UTF-8 解码器。

    feed() 喂任意分块的字节并返回本次解出的文本，分块方式不影响
    解码结果；flush() 在流结束时收尾。流首的 UTF-8 BOM 会被剥离，
    不出现在解码结果里。errors='strict' 遇到非法字节抛
    Utf8DecodeError；'replace' 用 U+FFFD 顶替坏字节本身，其后的
    字节照常解码。consumed 累计真正处理过的字节数，上游按它推进
    源读指针。
    """

    def __init__(self, errors: str = "replace"):
        if errors not in ("strict", "replace"):
            raise ValueError("errors 仅支持 strict / replace")
        self.errors = errors
        self.consumed = 0
        self._buf = bytearray()
        self._head = True

    def feed(self, chunk: bytes) -> str:
        if self._head and self._buf[:3] == _BOM:
            del self._buf[:3]
            self._head = False
        self._buf.extend(chunk)
        return self._drain()

    def flush(self) -> str:
        if self._head and self._buf[:3] == _BOM:
            del self._buf[:3]
            self._head = False
        return self._drain(tail=True)

    def _consume_bad(self, offset: int):
        """按错误策略处理 offset 处的坏字节，返回 (顶替文本, 吃掉的字节数)。"""
        if self.errors == "strict":
            raise Utf8DecodeError("offset %d 处的字节无法按 UTF-8 解码" % offset)
        return "�", len(self._buf) - offset

    def _drain(self, tail: bool = False) -> str:
        out = []
        i = 0
        buf = self._buf
        n = len(buf)
        while i < n:
            head = buf[i]
            need = _seq_len(head)
            if need == 1:
                out.append(chr(head))
                i += 1
                continue
            if need < 0 or i + need > n:
                if need > 0 and not tail:
                    break  # 序列没收全，等下一块
                text, used = self._consume_bad(i)
                out.append(text)
                i += used
                continue
            bad = -1
            for k in range(1, need):
                if buf[i + k] & 0xC0 != 0x80:
                    bad = k
                    break
            if bad >= 0:
                text, used = self._consume_bad(i + bad)
                out.append(text)
                i += bad + used
                continue
            if need == 2:
                cp = ((head & 0x1F) << 6) | (buf[i + 1] & 0x3F)
            elif need == 3:
                cp = ((head & 0x0F) << 12) | ((buf[i + 1] & 0x3F) << 6) | (buf[i + 2] & 0x3F)
            else:
                cp = ((head & 0x07) << 18) | ((buf[i + 1] & 0x3F) << 10) | ((buf[i + 2] & 0x3F) << 6) | (buf[i + 3] & 0x3F)
            if cp > 0x10FFFF:
                text, used = self._consume_bad(i)
                out.append(text)
                i += used
                continue
            out.append(chr(cp))
            i += need
        del self._buf[: i + 1]
        self.consumed += i
        return "".join(out)
