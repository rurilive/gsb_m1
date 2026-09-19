"""httpparse.parser：HTTP/1.1 请求解析的对外入口（请求头 + CL / chunked body）。

本模块只保留对外契约，实现拆成三层：

- constants.py：长度上限、CRLF、各处字节/整数字面量；
- tokenizer.py：按行切字节（行长在这层卡）+ 增量字节缓冲；
- message.py：MessageReader 状态机，请求行/头部/body 在显式状态上推进。

parse_request 仍是"一口气把整个请求吃完再返回"的语义；状态机本身是
增量的（每步只取需要的量，取不到返回 NEED_DATA），流式版本只需分段
feed + 反复 pump。

错误文本是契约的一部分（下游日志采集在正则匹配），别改。
"""

from httpparse.errors import ParseError
from httpparse.message import HttpRequest, MessageReader
from httpparse.tokenizer import LineTokenizer

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

    tokenizer = LineTokenizer()
    tokenizer.feed(data)
    return MessageReader(tokenizer).finish()
