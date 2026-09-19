"""httpparse.parser：对外门面（第三层的入口）。

2018 年的 HTTP/1.1 请求解析已拆成三层：
constants（字面量/上限）-> tokenizer（按行切字节、行长限制）
-> message（请求行/头部/body 状态推进）。
本模块只保留对外 API 的签名与行为：parse_request 一口气喂完，
内部走的就是流式同款 RequestAssembler，所以错误文本和容错口径
与历史完全一致（tests/ 锁定，下游日志在正则匹配报错文案）。
"""

from .message import HttpRequest, RequestAssembler
from .tokenizer import ParseError

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

    assembler = RequestAssembler()
    assembler.feed(data)
    return assembler.finish()
