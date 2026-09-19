"""解析错误类型。ParseError 是 ValueError 子类（对外契约，不可变）。"""


class ParseError(ValueError):
    """请求不合法。错误文本是契约的一部分（下游日志正则匹配），不可变。"""
