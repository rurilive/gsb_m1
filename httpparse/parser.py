"""httpparse.parser：对外兼容门面。

历史契约从这里导入 HttpRequest / ParseError / parse_request，签名和行为
保持不变。实现已拆成三层：constants（口径常量）、tokenizer（按行切字节、
行长限制）、message（请求行/头部/body 状态推进）；parse_request 只是把
一整段字节一次性喂给同一个流式状态机。
"""

from httpparse.errors import ParseError
from httpparse.message import HttpRequest, RequestReader

__all__ = ["HttpRequest", "ParseError", "parse_request"]


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

    reader = RequestReader()
    reader.feed(data)
    return reader.finish()
