"""effecteval 自有异常类型。

所有可诊断错误都继承 EvalError，带上出错表达式与字符下标。下标是 src 上的
字符偏移，从 0 起；message 是单行说明。副作用记录与回滚相关的错误后续也在
这一层扩展。
"""


class EvalError(Exception):
    """求值过程中所有可诊断错误的基类。

    src 是出错时的表达式原文，index 是 src 上的出错下标（字符偏移）。
    message 是单行说明。
    """

    def __init__(self, message, *, src="", index=0):
        super().__init__(message)
        self.message = message
        self.src = src
        self.index = index

    def __str__(self):
        return "%s (position %d)" % (self.message, self.index)


class ParseError(EvalError):
    """解析期错误：语法不合法或表达式非标准形式。"""


class EvalRuntimeError(EvalError):
    """求值期错误：除零、未定义变量等。"""


def error_at(exc_type, message, src, token):
    """按 token 的起始下标构造 exc_type，token 为 None 时退到 src 末尾。"""
    index = len(src) if token is None else token.start
    return exc_type(message, src=src, index=index)
