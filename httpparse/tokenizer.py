"""tokenizer 层：只管喂进来的原始字节。

职责只有两件：

1. 按行切字节：认 CRLF，也认裸 LF（历史容错），返回的行剥掉行结束符
   （行尾单个 CR 一并剥掉）；
2. 行长限制：长度按「行首到换行符之前」的字节数算（CRLF 时含 CR 不含
   LF），超过 MAX_LINE_LENGTH 就在这一层报错。

这一层不认识请求行、头部、chunk，只认字节和换行。数据可以一段一段
feed 进来：没拿到换行的尾巴留在缓冲里，等下一段拼上再切——所以它不
依赖"一口气吃完整个请求"。

body（固定字节数或 chunk 数据）不是行，由上层用 buffered_length /
take / starts_with / consume 直接从缓冲区取。
"""

from httpparse.constants import CR, LF, MAX_LINE_LENGTH
from httpparse.errors import ParseError


class LineTokenizer(object):
    """增量字节缓冲 + 行切分。

    next_line 只在确实看到换行符时返回一行；否则返回 None（数据还没到），
    调用方之后可以再 feed。enforce_length=False 时不在本层卡行长（trailer
    区历史上不限长，保持原行为）。
    """

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data):
        """追加一段字节。"""
        self._buf.extend(data)

    @property
    def buffered_length(self):
        """当前缓冲区里还没被取走的字节数。"""
        return len(self._buf)

    def next_line(self, enforce_length=True):
        """取下一行（不含行结束符）；没有完整行时返回 None。"""
        nl = self._buf.find(LF)
        if nl == -1:
            return None
        if enforce_length and nl > MAX_LINE_LENGTH:
            raise ParseError("line too long: %d bytes" % nl)
        line = bytes(self._buf[:nl])
        del self._buf[:nl + 1]
        if line and line[-1] == CR:
            line = line[:-1]
        return line

    def take(self, count):
        """取走缓冲区开头的 count 个字节；不足时返回 None（数据还没到）。"""
        if len(self._buf) < count:
            return None
        chunk = bytes(self._buf[:count])
        del self._buf[:count]
        return chunk

    def starts_with(self, expected):
        """缓冲区当前开头是否是 expected（不消费）。"""
        return self._buf[:len(expected)] == expected

    def peek(self, count):
        """看缓冲区开头最多 count 个字节（不消费），不足多少给多少。"""
        return bytes(self._buf[:count])

    def consume(self, count):
        """丢弃缓冲区开头的 count 个字节（调用方需确认够数）。"""
        del self._buf[:count]
