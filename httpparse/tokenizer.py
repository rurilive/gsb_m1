"""httpparse.tokenizer：按行切字节（第一层）。

只管字节，不懂 HTTP：把陆续喂进来的字节按 LF 切成行，剥掉行尾的
CRLF/裸 LF，行长上限在这层统一检查。支持一段段喂数据（流式），
没到行尾的尾巴留在缓冲区里等下一次 feed。
"""

from .constants import LF, LINE_TOO_LONG, MAX_LINE_LENGTH


class ParseError(ValueError):
    """请求不合法。

    定义在最底层，message/parser 各层复用同一个类（对外仍是
    ValueError 子类、仍是 httpparse.ParseError）。
    """


class LineTokenizer(object):
    """增量按行切分器。

    数据可一次喂完，也可分任意多次 feed；切出来的行不含行尾的
    \\r\\n 或 \\n。行长口径与历史一致：剥掉末尾 \\n 后还剩多少字节
    （含可能的 \\r）就算多少，超过 MAX_LINE_LENGTH 即报错。
    """

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data):
        self._buf.extend(data)

    def has_line(self):
        return self._buf.find(LF) != -1

    def take_line(self, enforce_limit=True):
        """取出下一行（不含换行符），没有完整行时返回 None。

        enforce_limit=False 时跳过行长检查——历史上 trailer 区的行
        不受 8192 约束，由组装层显式选择。
        """
        nl = self._buf.find(LF)
        if nl == -1:
            return None
        if enforce_limit and nl > MAX_LINE_LENGTH:
            raise ParseError(LINE_TOO_LONG % nl)
        line = bytes(self._buf[:nl])
        del self._buf[:nl + 1]
        if line.endswith(b"\r"):
            line = line[:-1]
        return line

    def pending_length(self):
        """缓冲区里尚未消费的字节数（body 定量读取用）。"""
        return len(self._buf)

    def take_bytes(self, n):
        """取走最多 n 个原始字节（body 段按长度消费）。"""
        chunk = bytes(self._buf[:n])
        del self._buf[:n]
        return chunk

    def peek_bytes(self, n):
        """看前 n 个字节但不消费（chunk 终止符判断用）。"""
        return bytes(self._buf[:n])

    def skip_bytes(self, n):
        del self._buf[:n]

    def take_rest(self):
        """取走并返回缓冲区剩余的全部字节（EOF 时的残缺尾行用）。"""
        rest = bytes(self._buf)
        self._buf.clear()
        return rest
