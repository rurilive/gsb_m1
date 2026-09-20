"""httpparse.errors：解析错误类型。

错误文本是契约的一部分（下游日志采集在正则匹配），一律不得改动。
"""


class ParseError(ValueError):
    """请求不合法。"""
