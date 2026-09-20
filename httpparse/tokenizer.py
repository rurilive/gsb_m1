"""httpparse.tokenizer：面向流式输入的按行切字节层。

只认字节，不认识 HTTP：数据可以分任意段 feed 进来，next_line 在凑到
换行符之前返回 None，凑到后返回去掉 LF（以及一个裸 CR）的整行。
行长度上限（含换行符的整行字节数，历史口径 MAX_LINE_LENGTH）在这层把关。
body 部分不走行概念，用 take_bytes / peek_bytes 按字节数推进。
"""

from httpparse import constants as C
from httpparse.errors import ParseError


class LineTokenizer(object):
    """带内部缓冲区的字节切行器，状态只在本对象内部。"""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data):
        """追加一段字节（流式到达时反复调用）。"""
        self._buf.extend(data)

    def next_line(self, enforce_length=True):
        """返回下一行（bytes，不含行结束符），没有完整行时返回 None。

        行结束符 CRLF 与裸 LF 都认（历史容错），只剥掉行尾一个 CR。
        enforce_length 为 True 时，LF 之前（含裸 CR）的整行字节数超过
        MAX_LINE_LENGTH 立即抛 "line too long"（历史口径与报错数值）；
        chunk trailer 等不设限的场景传 False。
        """
        nl = self._buf.find(C.LF)
        if nl == -1:
            return None
        if enforce_length and nl > C.MAX_LINE_LENGTH:
            raise ParseError("line too long: %d bytes" % nl)
        line = bytes(self._buf[:nl])
        del self._buf[:nl + 1]
        if line and line[-1] == C.CR_BYTE:
            line = line[:-1]
        return line

    def check_pending_limit(self):
        """无 LF 收尾时的行长校验：超 MAX_LINE_LENGTH 抛错。

        供头部阶段遇到 EOF 前调用，保持历史口径（裸数据按整行算）。
        """
        if len(self._buf) > C.MAX_LINE_LENGTH:
            raise ParseError("line too long: %d bytes" % len(self._buf))

    def pending_length(self):
        """当前未消费的裸字节数（body 边界计算用）。"""
        return len(self._buf)

    def has_data(self):
        return bool(self._buf)

    def peek_bytes(self, n):
        """看前 n 个字节但不消费（不足 n 时有多少给多少）。"""
        return bytes(self._buf[:n])

    def take_bytes(self, n):
        """消费前 n 个字节；不足 n 个抛 AssertionError（调用方先判长度）。"""
        if n > len(self._buf):
            raise AssertionError("take_bytes(%d) with only %d buffered" % (n, len(self._buf)))
        chunk = bytes(self._buf[:n])
        del self._buf[:n]
        return chunk
