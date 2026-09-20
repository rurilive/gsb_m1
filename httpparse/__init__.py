"""httpparse: 内部 HTTP/1.1 请求解析包。"""

from httpparse.parser import HttpRequest, ParseError, parse_request

__all__ = ["HttpRequest", "ParseError", "parse_request"]
