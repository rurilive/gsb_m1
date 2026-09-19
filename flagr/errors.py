"""flagr 的异常族。"""


class FlagrError(Exception):
    """本包所有错误的基类。"""


class RuleCompileError(FlagrError):
    """规则编译错误。message 之外带位置信息（行、列，均从 1 计）。"""

    def __init__(self, message, line, col):
        super().__init__(f"{line}:{col}: {message}")
        self.message = message
        self.line = line
        self.col = col


class UnknownFlagError(FlagrError):
    """求值了未定义的开关。"""

    def __init__(self, flag):
        super().__init__(f"未定义的开关 {flag!r}")
        self.flag = flag
